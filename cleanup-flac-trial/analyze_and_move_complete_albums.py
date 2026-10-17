"""Analyze FLAC album folders and optionally move complete albums by category/source."""

import argparse
import csv
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from mutagen.flac import FLAC
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise


CATEGORIES = ("Christian", "Secular", "Classical")
DEFAULT_SOURCE_RULES = {
    "spotify": "Spotify",
    "qobuz": "Qobuz",
    "tidal": "Tidal",
    "apple music": "AppleMusic",
    "amazon music": "AmazonMusic",
    "youtube music": "YouTubeMusic",
    "deezer": "Deezer",
}


@dataclass
class Album:
    source_path: Path
    artist: str
    album: str
    category: str
    source: str
    flac_files: list[Path]
    non_flac_files: list[Path]
    unreadable_files: list[Path]
    track_numbers: list[int]
    status: str = ""
    details: str = ""


def first_tag(audio: FLAC, *names: str) -> str:
    for name in names:
        values = audio.get(name)
        if values:
            return str(values[0]).strip()
    return ""


def classify_category(path: Path, genres: list[str], artists: list[str]) -> str:
    text = " ".join((str(path), *genres, *artists)).casefold()
    if any(word in text for word in ("classical", "orchestra", "symphony", "concerto", "sonata")):
        return "Classical"
    if any(word in text for word in ("christian", "gospel", "worship", "hymn", "praise")):
        return "Christian"
    if "secular" in text:
        return "Secular"
    return ""


def classify_source(path: Path, rules: dict[str, str]) -> str:
    text = str(path).casefold()
    for needle, destination in rules.items():
        if needle.casefold() in text:
            return destination
    return "UnclassifiedSource"


def safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(".")
    return cleaned or fallback


def album_candidates(root: Path) -> list[Path]:
    candidates = []
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: str(item).casefold()):
        if list(directory.glob("*.flac")) or list(directory.glob("*.FLAC")):
            candidates.append(directory)
    return candidates


def inspect_album(path: Path, rules: dict[str, str]) -> Album:
    files = sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: str(item).casefold())
    flac_files = [item for item in files if item.suffix.casefold() == ".flac"]
    non_flac_files = [item for item in files if item.suffix.casefold() != ".flac"]
    unreadable_files = []
    artists = []
    albums = []
    genres = []
    track_numbers = []

    for file_path in flac_files:
        audio = None
        try:
            audio = FLAC(file_path)
            artists.append(first_tag(audio, "albumartist", "artist"))
            albums.append(first_tag(audio, "album"))
            genres.append(first_tag(audio, "genre"))
            track = first_tag(audio, "tracknumber")
            if track:
                track_numbers.append(int(track.split("/")[0]))
        except (OSError, ValueError, TypeError):
            unreadable_files.append(file_path)
        finally:
            file_object = getattr(audio, "fileobj", None)
            if file_object is not None:
                file_object.close()

    artist = next((value for value in artists if value), path.parent.name)
    album = next((value for value in albums if value), path.name)
    category = classify_category(path, [value for value in genres if value], [value for value in artists if value])
    source = classify_source(path, rules)
    issues = []
    tracks_sequential = "unknown"
    if track_numbers:
        tracks_sequential = "yes" if sorted(set(track_numbers)) == list(range(1, max(track_numbers) + 1)) else "no"
    if not flac_files:
        issues.append("no FLAC files")
    if non_flac_files:
        issues.append("contains non-FLAC files")
    if unreadable_files:
        issues.append("contains unreadable FLAC files")
    if not category:
        issues.append("category unresolved")
    if tracks_sequential == "no":
        issues.append("track numbers are not contiguous")

    status = "complete" if not issues else "review"
    return Album(path, artist, album, category, source, flac_files, non_flac_files, unreadable_files, track_numbers, status, "; ".join(issues))


def non_flac_candidates(root: Path, destination_root: Path) -> list[tuple[Path, Path, list[Path]]]:
    candidates = []
    matched_directories = []
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: (len(item.parts), str(item).casefold())):
        destination = destination_root / directory.relative_to(root)
        if destination.is_dir() and not any(parent in matched_directories for parent in directory.parents):
            matched_directories.append(directory)
            files = sorted((item for item in directory.rglob("*") if item.is_file() and item.suffix.casefold() != ".flac"), key=lambda item: str(item).casefold())
            if files:
                candidates.append((directory, destination, files))
    return candidates


def parse_source_rules(values: list[str]) -> dict[str, str]:
    rules = dict(DEFAULT_SOURCE_RULES)
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("source rules must use needle=destination")
        needle, destination = value.split("=", 1)
        if not needle.strip() or not destination.strip():
            raise argparse.ArgumentTypeError("source rules must use a non-empty needle=destination")
        rules[needle.strip()] = safe_name(destination.strip(), "UnclassifiedSource")
    return rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-root", type=Path, default=Path(r"M:\MusicTrial\FlacTrial"))
    parser.add_argument("--destination-root", type=Path, default=Path(r"M:\MusicFlacSource"))
    parser.add_argument(
        "--move-sequential-to",
        type=Path,
        default=Path(r"M:\MusicTrialFlacFull"),
        help="Move albums with sequential track numbers to this root",
    )
    parser.add_argument("--move-non-flac", action="store_true", help="Move non-FLAC files to existing corresponding destination folders")
    parser.add_argument("--apply", action="store_true", help="Apply the selected collision-free album moves")
    parser.add_argument("--source-rule", action="append", default=[], metavar="TEXT=FOLDER", help="Additional source path rule")
    parser.add_argument("--report", type=Path, help="CSV report path")
    args = parser.parse_args()

    if not args.trial_root.is_dir():
        parser.error(f"trial root does not exist or is not a directory: {args.trial_root}")
    rules = parse_source_rules(args.source_rule)
    report = args.report or Path(__file__).with_name("analyze_and_move_complete_albums.csv")
    albums = [inspect_album(path, rules) for path in album_candidates(args.trial_root)]

    rows = []
    for album in albums:
        destination = ""
        tracks_sequential = (
            "yes"
            if album.track_numbers and sorted(set(album.track_numbers)) == list(range(1, max(album.track_numbers) + 1))
            else "no"
            if album.track_numbers
            else "unknown"
        )
        if args.move_sequential_to:
            if tracks_sequential == "yes":
                destination = args.move_sequential_to / album.source_path.relative_to(args.trial_root)
                if destination.exists():
                    album.status = "collision"
                    album.details = f"destination already exists: {destination}"
                else:
                    album.status = "sequential"
        elif album.status == "complete":
            destination = args.destination_root / album.category / album.source / safe_name(album.artist, "UnknownArtist") / safe_name(album.album, "UnknownAlbum")
            if destination.exists():
                album.status = "collision"
                album.details = f"destination already exists: {destination}"
        if album.status in {"complete", "sequential"} and args.apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(album.source_path), str(destination))
            album.status = "moved"
        rows.append({
            "source_path": str(album.source_path),
            "destination_path": str(destination),
            "artist": album.artist,
            "album": album.album,
            "category": album.category,
            "source": album.source,
            "flac_count": len(album.flac_files),
            "track_count": len(album.flac_files),
            "tracks_sequential": tracks_sequential,
            "non_flac_count": len(album.non_flac_files),
            "unreadable_count": len(album.unreadable_files),
            "status": album.status,
            "details": album.details,
        })

    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["source_path", "status", "details"])
        writer.writeheader()
        writer.writerows(rows)

    non_flac_moved = 0
    non_flac_collisions = 0
    if args.move_non_flac:
        for source_directory, destination_directory, files in non_flac_candidates(args.trial_root, args.move_sequential_to):
            for source_file in files:
                destination_file = destination_directory / source_file.relative_to(source_directory)
                if destination_file.exists():
                    non_flac_collisions += 1
                    continue
                if args.apply:
                    destination_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source_file), str(destination_file))
                    non_flac_moved += 1
                else:
                    non_flac_moved += 1

    counts = {status: sum(1 for album in albums if album.status == status) for status in ("complete", "sequential", "review", "collision", "moved")}
    print(f"Albums analyzed: {len(albums)}")
    print(f"Complete: {counts['complete']}  Sequential: {counts['sequential']}  Review: {counts['review']}  Collisions: {counts['collision']}  Moved: {counts['moved']}")
    if args.move_non_flac:
        print(f"Non-FLAC files moved: {non_flac_moved}  Non-FLAC collisions: {non_flac_collisions}")
    print(f"Report: {report}")
    if not args.apply:
        print("Dry run only. Re-run with --apply to apply the selected moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())