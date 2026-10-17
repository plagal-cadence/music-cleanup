"""Find the M: copies (MediaMonkey-moved FLACs and converted MP3s) of the full albums in E:\\MusicTrialFlacFull.

Report-only by default. With --apply, matched M: files are moved into a quarantine folder on M: (not deleted),
with a manifest that --restore can use to put everything back.
"""

import argparse
import csv
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise


AUDIO_SUFFIXES = {".flac", ".mp3", ".ape", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".wv", ".aiff", ".aif", ".dsf", ".dff"}
MP3_DURATION_TOLERANCE = 1.0
ZERO_MD5 = 0


@dataclass
class Track:
    path: Path
    md5: int = ZERO_MD5
    samples: int = 0
    length: float = 0.0
    album: str = ""
    title: str = ""
    track: int | None = None


def norm(value: str) -> str:
    return re.sub(r"\W+", "", value.casefold())


def track_number(value: str) -> int | None:
    match = re.match(r"\s*(\d+)", value)
    return int(match.group(1)) if match else None


def first_tag(tags, *names: str) -> str:
    for name in names:
        values = tags.get(name) if tags else None
        if values:
            return str(values[0]).strip()
    return ""


def read_flac(path: Path) -> Track | None:
    try:
        audio = FLAC(path)
    except Exception:
        return None
    return Track(
        path,
        audio.info.md5_signature,
        audio.info.total_samples,
        audio.info.length,
        first_tag(audio, "album"),
        first_tag(audio, "title"),
        track_number(first_tag(audio, "tracknumber")),
    )


def read_mp3(path: Path) -> Track | None:
    try:
        audio = MP3(path)
    except Exception:
        return None
    tag = lambda key: str(audio.tags[key].text[0]).strip() if audio.tags and key in audio.tags and audio.tags[key].text else ""
    return Track(path, length=audio.info.length, album=tag("TALB"), title=tag("TIT2"), track=track_number(tag("TRCK")))


def audio_files(root: Path, suffix: str) -> list[Path]:
    return sorted((item for item in root.rglob("*") if item.is_file() and item.suffix.casefold() == suffix), key=lambda item: str(item).casefold())


def progress(label: str, count: int) -> None:
    if count % 1000 == 0:
        print(f"  {label}: {count}", flush=True)


def index(paths: list[Path], reader, label: str) -> list[Track]:
    tracks = []
    for count, path in enumerate(paths, 1):
        progress(label, count)
        track = reader(path)
        if track:
            tracks.append(track)
    return tracks


def match_flac(source: Track, by_md5: dict[int, list[Track]], by_samples: dict[int, list[Track]]) -> tuple[Track | None, str]:
    if source.md5 != ZERO_MD5:
        hits = by_md5.get(source.md5, [])
        if len(hits) == 1:
            return hits[0], "audio md5"
        if len(hits) > 1:
            return None, f"audio md5 shared by {len(hits)} M: files"
    # Some encoders leave the MD5 empty; fall back to exact sample count plus title.
    hits = [item for item in by_samples.get(source.samples, []) if norm(item.title) == norm(source.title)]
    if len(hits) == 1:
        return hits[0], "sample count + title"
    if len(hits) > 1:
        return None, f"sample count + title shared by {len(hits)} M: files"
    return None, "no M: FLAC found"


def mirrored_mp3_dir(flac_path: Path, flac_root: Path, mp3_parent: Path) -> Path:
    parts = flac_path.parent.relative_to(flac_root).parts
    return mp3_parent.joinpath(parts[0], "MusicFromFlac", *parts[1:])


def match_mp3(reference: Track, folder: Path | None, by_dir: dict[str, list[Track]], by_album_title: dict[tuple[str, str], list[Track]]) -> tuple[Track | None, str]:
    def fits(item: Track) -> bool:
        return (
            norm(item.title) == norm(reference.title)
            and abs(item.length - reference.length) <= MP3_DURATION_TOLERANCE
            and (reference.track is None or item.track == reference.track)
        )

    if folder is not None:
        hits = [item for item in by_dir.get(str(folder).casefold(), []) if fits(item)]
        if len(hits) == 1:
            return hits[0], "mirrored folder + title + track + duration"
        if len(hits) > 1:
            return None, f"{len(hits)} MP3s fit in mirrored folder"
    hits = [item for item in by_album_title.get((norm(reference.album), norm(reference.title)), []) if fits(item)]
    if len(hits) == 1:
        return hits[0], "album + title + track + duration"
    if len(hits) > 1:
        return None, f"{len(hits)} MP3s fit by album + title"
    return None, "no MP3 found"


def folder_plan(matched: set[Path], top_folders: set[Path]) -> tuple[list[dict], list[Path]]:
    """Sidecar files move only when every audio file under that album folder was matched."""
    rows, sidecars = [], []
    for folder in sorted(top_folders, key=lambda item: str(item).casefold()):
        files = [item for item in folder.rglob("*") if item.is_file()]
        audio = [item for item in files if item.suffix.casefold() in AUDIO_SUFFIXES]
        unmatched = [item for item in audio if item not in matched]
        others = [item for item in files if item.suffix.casefold() not in AUDIO_SUFFIXES]
        complete = not unmatched
        if complete:
            sidecars.extend(others)
        rows.append({
            "folder": str(folder),
            "audio_files": len(audio),
            "matched_audio": len(audio) - len(unmatched),
            "unmatched_audio": len(unmatched),
            "sidecar_files": len(others),
            "action": "quarantine folder" if complete else "quarantine matched audio only; review",
            "unmatched_examples": "; ".join(item.name for item in unmatched[:5]),
        })
    return rows, sidecars


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def quarantine(paths: list[Path], quarantine_root: Path, manifest: Path) -> int:
    moved = []
    for source in sorted(set(paths), key=lambda item: str(item).casefold()):
        if not source.is_file():
            continue
        destination = quarantine_root / Path(*source.parts[1:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved.append({"original_path": str(source), "quarantine_path": str(destination)})
    write_csv(manifest, moved)
    return len(moved)


def restore(manifest: Path) -> int:
    restored = 0
    with manifest.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            source, destination = Path(row["quarantine_path"]), Path(row["original_path"])
            if source.is_file() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                restored += 1
    return restored


def remove_empty_dirs(folders: list[Path], stop_at: list[Path]) -> None:
    """Remove empty folders under each folder, then empty parents up to (not including) the library roots."""
    for folder in sorted(folders, key=lambda item: len(item.parts), reverse=True):
        if not folder.is_dir():
            continue
        for directory in sorted((item for item in folder.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()
        current = folder
        while current not in stop_at and current.parent != current and current.is_dir() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-root", type=Path, default=Path(r"E:\MusicTrialFlacFull"))
    parser.add_argument("--flac-root", type=Path, default=Path(r"M:\MusicFlac"))
    parser.add_argument("--mp3-root", type=Path, default=Path(r"M:\MusicMp3"), help="Searched only under <category>\\MusicFromFlac")
    parser.add_argument("--trial-leftovers", type=Path, default=Path(r"M:\MusicTrialFlacFull"))
    parser.add_argument("--quarantine-root", type=Path, default=Path(r"M:\_DeleteQueue"))
    parser.add_argument("--apply", action="store_true", help="Move matched M: files into the quarantine folder")
    parser.add_argument("--restore", type=Path, metavar="MANIFEST", help="Move files from a quarantine manifest back to their original paths")
    args = parser.parse_args()
    here = Path(__file__).parent

    if args.restore:
        print(f"Restored: {restore(args.restore)}")
        return 0
    for root in (args.source_root, args.flac_root, args.mp3_root):
        if not root.is_dir():
            parser.error(f"folder does not exist: {root}")

    print("Reading E: FLACs...")
    sources = index(audio_files(args.source_root, ".flac"), read_flac, "E: FLAC")
    print("Reading M: FLACs...")
    m_flacs = index(audio_files(args.flac_root, ".flac"), read_flac, "M: FLAC")
    print("Reading M: converted MP3s...")
    mp3_roots = sorted(args.mp3_root.glob("*/MusicFromFlac"))
    m_mp3s = index([path for root in mp3_roots for path in audio_files(root, ".mp3")], read_mp3, "M: MP3")

    by_md5, by_samples = defaultdict(list), defaultdict(list)
    for item in m_flacs:
        if item.md5 != ZERO_MD5:
            by_md5[item.md5].append(item)
        by_samples[item.samples].append(item)
    by_dir, by_album_title = defaultdict(list), defaultdict(list)
    for item in m_mp3s:
        by_dir[str(item.path.parent).casefold()].append(item)
        by_album_title[(norm(item.album), norm(item.title))].append(item)

    rows, matched = [], set()
    flac_folders, mp3_folders = set(), set()
    mp3_claims = defaultdict(list)
    for source in sources:
        m_flac, flac_how = match_flac(source, by_md5, by_samples)
        reference = m_flac or source
        folder = mirrored_mp3_dir(m_flac.path, args.flac_root, args.mp3_root) if m_flac else None
        m_mp3, mp3_how = match_mp3(reference, folder, by_dir, by_album_title)
        if m_flac:
            matched.add(m_flac.path)
            flac_folders.add(m_flac.path.parent)
        if m_mp3:
            mp3_claims[m_mp3.path].append(source.path)
            mp3_folders.add(m_mp3.path.parent)
        rows.append({
            "e_flac": str(source.path),
            "m_flac": str(m_flac.path) if m_flac else "",
            "flac_match": flac_how,
            "m_mp3": str(m_mp3.path) if m_mp3 else "",
            "mp3_match": mp3_how,
            "mp3_seconds_diff": f"{m_mp3.length - reference.length:.2f}" if m_mp3 else "",
        })

    # An MP3 claimed by more than one E: track is not trusted.
    for row in rows:
        if row["m_mp3"] and len(mp3_claims[Path(row["m_mp3"])]) > 1:
            row["mp3_match"] = f"rejected: claimed by {len(mp3_claims[Path(row['m_mp3'])])} E: tracks"
            row["m_mp3"] = ""
    matched.update(Path(row["m_mp3"]) for row in rows if row["m_mp3"])

    folder_rows, sidecars = folder_plan(matched, flac_folders | mp3_folders)
    leftovers = []
    if args.trial_leftovers.is_dir():
        leftover_files = [item for item in args.trial_leftovers.rglob("*") if item.is_file()]
        leftover_audio = [item for item in leftover_files if item.suffix.casefold() in AUDIO_SUFFIXES]
        folder_rows.append({
            "folder": str(args.trial_leftovers),
            "audio_files": len(leftover_audio),
            "matched_audio": 0,
            "unmatched_audio": len(leftover_audio),
            "sidecar_files": len(leftover_files) - len(leftover_audio),
            "action": "quarantine folder" if not leftover_audio else "contains audio; review",
            "unmatched_examples": "; ".join(item.name for item in leftover_audio[:5]),
        })
        if not leftover_audio:
            leftovers = leftover_files

    # Folders with no E: counterpart that should still be quarantined, one path per line.
    extras, extra_folders = [], []
    extra_list = here / "compare_full_albums_e_vs_m_extra.txt"
    if extra_list.is_file():
        for line in extra_list.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            folder = Path(line.strip())
            files = [item for item in folder.rglob("*") if item.is_file()] if folder.is_dir() else []
            audio = [item for item in files if item.suffix.casefold() in AUDIO_SUFFIXES]
            folder_rows = [row for row in folder_rows if Path(row["folder"]) != folder]
            folder_rows.append({
                "folder": str(folder),
                "audio_files": len(audio),
                "matched_audio": sum(1 for item in audio if item in matched),
                "unmatched_audio": 0,
                "sidecar_files": len(files) - len(audio),
                "action": f"quarantine folder (listed in {extra_list.name})" if folder.is_dir() else f"missing (listed in {extra_list.name})",
                "unmatched_examples": "",
            })
            extras.extend(files)
            extra_folders.append(folder)

    files_report = here / "compare_full_albums_e_vs_m_files.csv"
    folders_report = here / "compare_full_albums_e_vs_m_folders.csv"
    write_csv(files_report, rows)
    write_csv(folders_report, folder_rows)

    flac_hits = sum(1 for row in rows if row["m_flac"])
    mp3_hits = sum(1 for row in rows if row["m_mp3"])
    partial = sum(1 for row in folder_rows if row["unmatched_audio"])
    print(f"E: FLACs: {len(sources)}  M: FLAC matches: {flac_hits}  M: MP3 matches: {mp3_hits}")
    print(f"M: folders involved: {len(folder_rows)}  needing review (contain unmatched audio): {partial}")
    print(f"Files to quarantine: {len(matched)} audio + {len(sidecars) + len(leftovers)} sidecar + {len(extras)} from {extra_list.name}")
    print(f"Reports: {files_report}\n         {folders_report}")

    if not args.apply:
        print("Report only. Re-run with --apply to move matched M: files into quarantine.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest = here / f"compare_full_albums_e_vs_m_quarantine_{stamp}.csv"
    moved = quarantine([*matched, *sidecars, *leftovers, *extras], args.quarantine_root / stamp, manifest)
    stop_at = [args.flac_root, args.mp3_root, *mp3_roots, *args.flac_root.iterdir(), *args.mp3_root.iterdir(), args.trial_leftovers.parent]
    remove_empty_dirs([args.trial_leftovers, *flac_folders, *mp3_folders, *extra_folders], stop_at)
    print(f"Quarantined: {moved}  Manifest: {manifest}")
    print(f"Undo with: --restore \"{manifest}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
