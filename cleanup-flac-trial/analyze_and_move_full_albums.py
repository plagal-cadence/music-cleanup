"""Find full FLAC albums on the E: drive and optionally move them, preserving their relative paths."""

import argparse
import csv
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    from mutagen.flac import FLAC
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise


AUDIO_SUFFIXES = {".mp3", ".ape", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".wv", ".aiff", ".aif", ".alac", ".dsf", ".dff"}
DISC_FOLDER = re.compile(r"^(?:cd|disc|disk)\s*[-_.]?\s*(\d+)\b", re.IGNORECASE)
DISC_SUFFIX = re.compile(r"[\s\-_(\[]*(?:cd|disc|disk)\s*\d+[)\]]?\s*$", re.IGNORECASE)
CUE_FILE = re.compile(r'^\s*FILE\s+"?(.+?)"?\s+\w+\s*$', re.IGNORECASE | re.MULTILINE)


@dataclass
class Album:
    source_path: Path
    folders: list[Path]
    artist: str = ""
    album: str = ""
    flac_files: list[Path] = field(default_factory=list)
    image_files: list[Path] = field(default_factory=list)
    extra_audio_files: list[Path] = field(default_factory=list)
    sidecar_files: list[Path] = field(default_factory=list)
    unreadable_files: list[Path] = field(default_factory=list)
    discs: dict[int, list[int]] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    status: str = ""


def first_tag(audio: FLAC, *names: str) -> str:
    for name in names:
        values = audio.get(name)
        if values:
            return str(values[0]).strip()
    return ""


def parse_number(value: str) -> tuple[int | None, int | None]:
    """Parse '3', '3/12', or '03 of 12' into (number, total)."""
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    if not numbers:
        return None, None
    return numbers[0], numbers[1] if len(numbers) > 1 else None


def has_flac(directory: Path) -> bool:
    return any(item.is_file() and item.suffix.casefold() == ".flac" for item in directory.iterdir())


def cue_images(files: list[Path]) -> set[Path]:
    """Return FLAC disc images referenced by a .cue file in the same folder as split tracks."""
    images = set()
    for cue in (item for item in files if item.suffix.casefold() == ".cue"):
        try:
            text = cue.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in CUE_FILE.findall(text):
            image = cue.parent / name
            split_tracks = [item for item in files if item.parent == cue.parent and item.suffix.casefold() == ".flac" and item.name.casefold() != name.casefold()]
            if image.suffix.casefold() == ".flac" and image.is_file() and split_tracks:
                images.add(image)
    return images


def album_groups(root: Path) -> list[Album]:
    """Group FLAC folders into albums; disc folders (CD1, Disc 2, ...) are merged into their parent."""
    flac_dirs = sorted((item for item in [root, *root.rglob("*")] if item.is_dir() and has_flac(item)), key=lambda item: str(item).casefold())
    groups: dict[Path, list[Path]] = defaultdict(list)
    for directory in flac_dirs:
        parent = directory.parent
        if directory != root and DISC_FOLDER.match(directory.name) and parent not in flac_dirs:
            groups[parent].append(directory)
        else:
            groups[directory].append(directory)
    return [Album(path, folders) for path, folders in sorted(groups.items(), key=lambda item: str(item[0]).casefold())]


def inspect_album(album: Album, all_album_paths: set[Path]) -> None:
    files = []
    for folder in album.folders:
        files.extend(item for item in folder.iterdir() if item.is_file())
    if album.folders != [album.source_path]:
        files.extend(item for item in album.source_path.iterdir() if item.is_file())
    files.sort(key=lambda item: str(item).casefold())

    images = cue_images(files)
    album.image_files = sorted(images, key=lambda item: str(item).casefold())
    album.flac_files = [item for item in files if item.suffix.casefold() == ".flac" and item not in images]
    album.extra_audio_files = [item for item in files if item.suffix.casefold() in AUDIO_SUFFIXES]
    album.sidecar_files = [item for item in files if item.suffix.casefold() != ".flac" and item.suffix.casefold() not in AUDIO_SUFFIXES]

    artists = []
    album_names: dict[Path, set[str]] = defaultdict(set)
    declared_tracks: dict[int, set[int]] = defaultdict(set)
    declared_discs: set[int] = set()
    missing_track_numbers = 0
    disc_tracks: dict[int, list[int]] = defaultdict(list)
    folder_disc = {folder: int(match.group(1)) for folder in album.folders if (match := DISC_FOLDER.match(folder.name))}

    for file_path in album.flac_files:
        audio = None
        try:
            audio = FLAC(file_path)
            artists.append(first_tag(audio, "albumartist", "artist"))
            name = first_tag(audio, "album")
            if name:
                album_names[file_path.parent].add(DISC_SUFFIX.sub("", name).casefold())
            track, track_total = parse_number(first_tag(audio, "tracknumber"))
            disc, disc_total = parse_number(first_tag(audio, "discnumber"))
            disc = disc or folder_disc.get(file_path.parent, 1)
            track_total = track_total or parse_number(first_tag(audio, "tracktotal", "totaltracks"))[0]
            disc_total = disc_total or parse_number(first_tag(audio, "disctotal", "totaldiscs"))[0]
            if track is None:
                missing_track_numbers += 1
                continue
            disc_tracks[disc].append(track)
            if track_total:
                declared_tracks[disc].add(track_total)
            if disc_total:
                declared_discs.add(disc_total)
        except (OSError, ValueError, TypeError):
            album.unreadable_files.append(file_path)
        finally:
            file_object = getattr(audio, "fileobj", None)
            if file_object is not None:
                file_object.close()

    album.artist = next((value for value in artists if value), album.source_path.parent.name)
    album.album = album.source_path.name
    album.discs = dict(sorted(disc_tracks.items()))

    for disc, tracks in album.discs.items():
        expected_count = max([max(tracks), *declared_tracks[disc]])
        gaps = sorted(set(range(1, expected_count + 1)) - set(tracks))
        if gaps:
            album.missing.append(f"disc {disc}: " + ",".join(str(item) for item in gaps))
        if len(tracks) != len(set(tracks)):
            album.issues.append(f"duplicate track numbers on disc {disc}")
        if len(declared_tracks[disc]) > 1:
            album.issues.append(f"conflicting track totals on disc {disc}")
    expected_discs = max([max(album.discs, default=0), *declared_discs])
    missing_discs = sorted(set(range(1, expected_discs + 1)) - set(album.discs))
    if missing_discs:
        album.missing.append("discs " + ",".join(str(item) for item in missing_discs))

    if album.missing:
        album.issues.append("missing tracks or discs")
    if missing_track_numbers:
        album.issues.append(f"{missing_track_numbers} FLAC files without track numbers")
    if album.unreadable_files:
        album.issues.append("contains unreadable FLAC files")
    if album.extra_audio_files:
        album.issues.append("contains non-FLAC audio files")
    if any(len(names) > 1 for names in album_names.values()):
        album.issues.append("files tagged with more than one album")
    if any(other != album.source_path and album.source_path in other.parents for other in all_album_paths):
        album.issues.append("contains nested album folders")
    album.status = "full" if not album.issues else "incomplete"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-root", type=Path, default=Path(r"E:\MusicTrial\FlacTrial"))
    parser.add_argument("--destination-root", type=Path, default=Path(r"E:\MusicTrialFlacFull"))
    parser.add_argument("--apply", action="store_true", help="Move full, collision-free albums")
    parser.add_argument("--report", type=Path, help="CSV report path")
    args = parser.parse_args()

    if not args.trial_root.is_dir():
        parser.error(f"trial root does not exist or is not a directory: {args.trial_root}")
    report = args.report or Path(__file__).with_name("analyze_and_move_full_albums.csv")

    albums = album_groups(args.trial_root)
    album_paths = {album.source_path for album in albums}
    for album in albums:
        inspect_album(album, album_paths)

    rows = []
    for album in albums:
        destination = ""
        if album.status == "full":
            destination = args.destination_root / album.source_path.relative_to(args.trial_root)
            if destination.exists():
                album.status = "collision"
                album.issues.append(f"destination already exists: {destination}")
            elif args.apply:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(album.source_path), str(destination))
                album.status = "moved"
        rows.append({
            "source_path": str(album.source_path),
            "destination_path": str(destination),
            "artist": album.artist,
            "album": album.album,
            "disc_count": len(album.discs),
            "flac_count": len(album.flac_files),
            "cue_image_count": len(album.image_files),
            "missing": "; ".join(album.missing),
            "extra_audio_count": len(album.extra_audio_files),
            "sidecar_count": len(album.sidecar_files),
            "unreadable_count": len(album.unreadable_files),
            "status": album.status,
            "details": "; ".join(album.issues),
        })

    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["source_path", "status", "details"])
        writer.writeheader()
        writer.writerows(rows)

    counts = {status: sum(1 for album in albums if album.status == status) for status in ("full", "incomplete", "collision", "moved")}
    print(f"Albums analyzed: {len(albums)}")
    print(f"Full: {counts['full']}  Incomplete: {counts['incomplete']}  Collisions: {counts['collision']}  Moved: {counts['moved']}")
    print(f"Report: {report}")
    if not args.apply:
        print("Dry run only. Re-run with --apply to move full albums.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
