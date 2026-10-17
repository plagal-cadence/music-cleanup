"""Dry-run MusicBrainz artist cleanup from FLAC sources to matching MP3s."""

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    from mutagen.flac import FLAC
    from mutagen.mp3 import MP3
except ImportError:
    print(
        "This process requires mutagen. Install it with: python -m pip install mutagen",
        file=sys.stderr,
    )
    raise


@dataclass(frozen=True)
class RootMapping:
    flac_sources: tuple[Path, ...]
    mp3_destinations: tuple[Path, ...]


ROOT_MAPPINGS = [
    # Classical from CDs
    RootMapping(
        flac_sources=(
            Path(r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac"),
            Path(r"M:\MusicFromCDsRussFlac\_Secular"),
        ),
        mp3_destinations=(Path(r"M:\Music\Secular\MusicFromCDsFromFlac"),),
    ),
    RootMapping(
        flac_sources=(Path(r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac"),),
        mp3_destinations=(Path(r"M:\Music\Christian\MusicFromCDsFromFlac"),),
    ),
    RootMapping(
        flac_sources=(
            Path(r"M:\MusicFlacSource\Classical\MusicFromCDs"),
            Path(r"M:\MusicFromCDsRussFlac\_Classical"),
        ),
        mp3_destinations=(Path(r"M:\Music\Classical\MusicFromCDsFromFlac"),),
    ),
]
VARIOUS_VALUES = {"various", "variousartists"}
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording/"
MUSICBRAINZ_USER_AGENT = "music-cleanup-dry-run/1.0 (local library audit)"
MUSICBRAINZ_TIMEOUT_SECONDS = 8
CACHE_VERSION = 4


def progress(current: int, total: int, label: str) -> None:
    percent = current / total if total else 1
    filled = int(40 * percent)
    line = f"{label} [{'#' * filled}{'-' * (40 - filled)}] {percent:6.1%} ({current}/{total})"
    if sys.stdout.isatty():
        print(f"\r{line}", end="", flush=True)
    else:
        print(line, flush=True)


def first_tag(audio: FLAC | MP3, name: str) -> str:
    values = audio.get(name) or []
    if not values:
        return ""
    value = values[0]
    text_values = getattr(value, "text", None)
    return str(text_values[0] if text_values else value).strip()


def normalize(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def fuzzy_same(left: str, right: str) -> bool:
    from difflib import SequenceMatcher

    left_normalized = normalize(left)
    right_normalized = normalize(right)
    return bool(
        left_normalized
        and right_normalized
        and SequenceMatcher(None, left_normalized, right_normalized).ratio() >= 0.9
    )


def title_candidates(title: str) -> list[str]:
    candidates = [title]
    candidates.extend(
        part.strip() for part in re.split(r"\s*(?:/|\\|\s+-\s+)\s*", title)
    )
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def read_audio_tags(file_path: Path) -> dict[str, str]:
    audio = None
    try:
        if file_path.suffix.casefold() == ".mp3":
            audio = MP3(file_path)
            return {
                "artist": first_tag(audio, "TPE1"),
                "album_artist": first_tag(audio, "TPE2"),
                "title": first_tag(audio, "TIT2"),
                "album": first_tag(audio, "TALB"),
            }
        audio = FLAC(file_path)
        return {
            "artist": first_tag(audio, "artist"),
            "album_artist": first_tag(audio, "albumartist"),
            "title": first_tag(audio, "title"),
            "album": first_tag(audio, "album"),
        }
    finally:
        file_object = getattr(audio, "fileobj", None)
        if file_object is not None:
            file_object.close()


def build_scan_cache(cache_path: Path) -> dict:
    cache = {"version": CACHE_VERSION, "sources": [], "mp3_index": {}}
    mp3_index: dict[str, list[dict[str, str]]] = {}
    mp3_files_by_mapping = []
    flac_files_by_mapping = []
    for root_mapping in ROOT_MAPPINGS:
        mp3_files_by_mapping.append(
            [
                path
                for destination in root_mapping.mp3_destinations
                for path in destination.rglob("*")
                if path.is_file() and path.suffix.casefold() == ".mp3"
            ]
        )
        flac_files_by_mapping.append(
            [
                (root, path)
                for root in root_mapping.flac_sources
                for path in root.rglob("*")
                if path.is_file() and path.suffix.casefold() == ".flac"
            ]
        )
    total_files = sum(len(files) for files in mp3_files_by_mapping) + sum(
        len(files) for files in flac_files_by_mapping
    )
    scanned_files = 0
    for mp3_files, flac_files in zip(mp3_files_by_mapping, flac_files_by_mapping):
        for mp3_path in mp3_files:
            scanned_files += 1
            progress(scanned_files, total_files, "Scanning library")
            try:
                tags = read_audio_tags(mp3_path)
            except (OSError, ValueError, TypeError):
                continue
            key = f"{normalize(tags['album'] or mp3_path.parent.name)}\x00{normalize(mp3_path.stem)}"
            mp3_index.setdefault(key, []).append(
                {
                    "path": str(mp3_path),
                    "artist": tags["artist"],
                    "album_artist": tags["album_artist"],
                }
            )
        for source_root, flac_path in flac_files:
            scanned_files += 1
            progress(scanned_files, total_files, "Scanning library")
            try:
                tags = read_audio_tags(flac_path)
            except (OSError, ValueError, TypeError) as error:
                tags = {
                    "artist": "",
                    "album_artist": "",
                    "title": "",
                    "album": "",
                    "error": str(error),
                }
            cache["sources"].append(
                {
                    "path": str(flac_path),
                    "root": str(source_root),
                    "destination": str(root_mapping.mp3_destinations[0]),
                    "tags": tags,
                }
            )
    print()
    cache["mp3_index"] = mp3_index
    cache_path.write_text(json.dumps(cache, ensure_ascii=True), encoding="utf-8")
    return cache


def load_scan_cache(cache_path: Path, rebuild: bool) -> dict:
    if rebuild or not cache_path.exists():
        print(f"Building scan cache: {cache_path}")
        return build_scan_cache(cache_path)
    print(f"Using scan cache: {cache_path}")
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache.get("version") != CACHE_VERSION:
        return build_scan_cache(cache_path)
    return cache


def musicbrainz_artists(
    title: str, album: str, cache: dict[str, list[str]]
) -> list[str]:
    for query_title in title_candidates(title):
        key = f"{album}\x00{query_title}"
        if key in cache:
            artists = cache[key]
        else:
            query = f'recording:"{query_title}"' + (
                f' AND release:"{album}"' if album else ""
            )
            url = (
                MUSICBRAINZ_URL
                + "?"
                + urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 10})
            )
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": MUSICBRAINZ_USER_AGENT,
                    "Accept": "application/json",
                },
            )
            artists = []
            try:
                with urllib.request.urlopen(
                    request, timeout=MUSICBRAINZ_TIMEOUT_SECONDS
                ) as response:
                    payload = json.load(response)
            except (OSError, ValueError, TimeoutError):
                payload = {}
            for recording in payload.get("recordings", []):
                if not fuzzy_same(recording.get("title", ""), query_title):
                    continue
                for credit in recording.get("artist-credit", []):
                    name = str(credit.get("name", "")).strip()
                    if (
                        name
                        and normalize(name) not in VARIOUS_VALUES
                        and name not in artists
                    ):
                        artists.append(name)
            cache[key] = artists
            time.sleep(1.1)
        if len(artists) == 1:
            return artists
    return []


def process_source(
    record: dict, mp3_index: dict, online_cache: dict[str, list[str]]
) -> dict | None:
    tags = record["tags"]
    if "error" in tags:
        return {
            "flac_path": record["path"],
            "mp3_path": "",
            "source_root": record["root"],
            "album": "",
            "title": "",
            "flac_artist_before": "",
            "flac_album_artist_before": "",
            "flac_artist_after": "",
            "flac_album_artist_after": "",
            "mp3_artist_before": "",
            "mp3_album_artist_before": "",
            "mp3_artist_after": "",
            "mp3_album_artist_after": "",
            "validated_artists": "",
            "status": "unreadable",
            "details": tags["error"],
        }
    if (
        normalize(tags["artist"]) not in VARIOUS_VALUES
        or normalize(tags["album_artist"]) not in VARIOUS_VALUES
    ):
        return None
    key = f"{normalize(tags['album'] or Path(record['path']).parent.name)}\x00{normalize(Path(record['path']).stem)}"
    matches = mp3_index.get(key, [])
    row = {
        "flac_path": record["path"],
        "mp3_path": matches[0]["path"] if len(matches) == 1 else "",
        "source_root": record["root"],
        "album": tags["album"],
        "title": tags["title"],
        "flac_artist_before": tags["artist"],
        "flac_album_artist_before": tags["album_artist"],
        "flac_artist_after": "",
        "flac_album_artist_after": "",
        "mp3_artist_before": matches[0]["artist"] if len(matches) == 1 else "",
        "mp3_album_artist_before": (
            matches[0]["album_artist"] if len(matches) == 1 else ""
        ),
        "mp3_artist_after": "",
        "mp3_album_artist_after": "",
        "validated_artists": "",
        "status": "",
        "details": "",
    }
    if len(matches) != 1:
        row["status"] = "review"
        row["details"] = (
            "no unique matching MP3" if not matches else f"{len(matches)} matching MP3s"
        )
        return row
    artists = musicbrainz_artists(tags["title"], tags["album"], online_cache)
    row["validated_artists"] = "; ".join(artists)
    if len(artists) != 1:
        row["status"] = "review"
        row["details"] = "MusicBrainz returned no unique artist"
    else:
        row["flac_artist_after"] = artists[0]
        row["flac_album_artist_after"] = "Various"
        row["mp3_artist_after"] = artists[0]
        row["mp3_album_artist_after"] = "Various"
        row["status"] = "would_update"
        row["details"] = (
            "MusicBrainz Artist and Album Artist would be applied to both FLAC and MP3"
        )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).with_name("01-various_artists_album_review.csv"),
    )
    parser.add_argument(
        "--scan-cache",
        type=Path,
        default=Path(__file__).with_name("01-various_artists_scan.json"),
    )
    parser.add_argument(
        "--rebuild-scan",
        action="store_true",
        help="Rescan FLAC and MP3 files before processing",
    )
    args = parser.parse_args()
    for root_mapping in ROOT_MAPPINGS:
        for root in (*root_mapping.flac_sources, *root_mapping.mp3_destinations):
            if not root.is_dir():
                parser.error(f"root does not exist or is not a directory: {root}")
    scan = load_scan_cache(args.scan_cache, args.rebuild_scan)
    albums: dict[tuple[str, str], dict[str, object]] = {}
    for record in scan["sources"]:
        tags = record["tags"]
        if (
            "error" in tags
            or normalize(tags["artist"]) not in VARIOUS_VALUES
            or normalize(tags["album_artist"]) not in VARIOUS_VALUES
        ):
            continue
        album = tags["album"] or Path(record["path"]).parent.name
        key = (record["root"], normalize(album))
        entry = albums.setdefault(
            key,
            {
                "source_root": record["root"],
                "destination": record.get("destination", ""),
                "album": album,
                "track_count": 0,
                "paths": [],
            },
        )
        entry["track_count"] += 1
        entry["paths"].append(record["path"])
    rows = [
        {
            "source_root": entry["source_root"],
            "mp3_destination": entry["destination"],
            "album": entry["album"],
            "track_count": entry["track_count"],
            "example_flac": entry["paths"][0],
            "filename_format": "",
            "status": "choose_format",
            "details": "Enter Title-Artist or Artist-Title in filename_format, then run the track script",
        }
        for entry in albums.values()
    ]
    print()
    fields = [
        "source_root",
        "mp3_destination",
        "album",
        "track_count",
        "example_flac",
        "filename_format",
        "status",
        "details",
    ]
    try:
        report_path = args.report
        handle = report_path.open("w", newline="", encoding="utf-8")
    except PermissionError:
        report_path = args.report.with_name(
            f"{args.report.stem}_rerun{args.report.suffix}"
        )
        print(
            f"Warning: {args.report} is locked; writing {report_path} instead.",
            file=sys.stderr,
        )
        handle = report_path.open("w", newline="", encoding="utf-8")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Albums requiring format decisions: {len(rows)}")
    print(f"Dry-run report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
