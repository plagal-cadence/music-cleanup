"""Scan the FLAC sources for tracks tagged Various in both Artist and Album Artist.

Writes 01-various_artists_scan.json: the candidate FLAC tracks plus an index of
every MP3 under the matching destinations, so later steps need no disk access.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from roots import ROOT_MAPPINGS
from tags import is_various, normalize, progress, read_audio_tags, use_utf8_stdout

CACHE_VERSION = 1


def mp3_keys(album: str, path: Path) -> tuple[str, str]:
    """Primary key uses the album tag, secondary falls back to the folder name."""
    stem = normalize(path.stem)
    return (
        f"{normalize(album or path.parent.name)}\x00{stem}",
        f"{normalize(path.parent.name)}\x00{stem}",
    )


def collect(root: Path, suffix: str) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() == suffix
    ]


def main() -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("01-various_artists_scan.json")
    )
    args = parser.parse_args()

    for mapping in ROOT_MAPPINGS:
        for root in (*mapping.flac_sources, *mapping.mp3_destinations):
            if not root.is_dir():
                parser.error(f"root does not exist or is not a directory: {root}")

    print("Enumerating files...")
    work = []
    for mapping in ROOT_MAPPINGS:
        flac_files = [
            (root, path) for root in mapping.flac_sources for path in collect(root, ".flac")
        ]
        mp3_files = [
            path for dest in mapping.mp3_destinations for path in collect(dest, ".mp3")
        ]
        work.append((mapping, flac_files, mp3_files))
    total = sum(len(flac) + len(mp3) for _, flac, mp3 in work)
    print(f"Found {total} audio files across {len(ROOT_MAPPINGS)} root mappings.")

    sources: list[dict] = []
    mp3_index: dict[str, list[dict]] = {}
    mp3_fallback: dict[str, list[dict]] = {}
    stats = Counter()
    scanned = 0

    for mapping, flac_files, mp3_files in work:
        destination = str(mapping.mp3_destinations[0])
        for mp3_path in mp3_files:
            scanned += 1
            progress(scanned, total, "Scanning library")
            try:
                mp3_tags = read_audio_tags(mp3_path)
            except (OSError, ValueError, TypeError):
                stats["mp3_unreadable"] += 1
                continue
            entry = {
                "path": str(mp3_path),
                "artist": mp3_tags["artist"],
                "album_artist": mp3_tags["album_artist"],
            }
            primary, secondary = mp3_keys(mp3_tags["album"], mp3_path)
            mp3_index.setdefault(primary, []).append(entry)
            if secondary != primary:
                mp3_fallback.setdefault(secondary, []).append(entry)

        for source_root, flac_path in flac_files:
            scanned += 1
            progress(scanned, total, "Scanning library")
            try:
                flac_tags = read_audio_tags(flac_path)
            except (OSError, ValueError, TypeError) as error:
                stats["flac_unreadable"] += 1
                sources.append(
                    {
                        "path": str(flac_path),
                        "root": str(source_root),
                        "destination": destination,
                        "error": str(error),
                    }
                )
                continue
            artist_various = is_various(flac_tags["artist"])
            album_artist_various = is_various(flac_tags["album_artist"])
            if not artist_various:
                stats["album_artist_various_only"] += album_artist_various
                stats["skipped_real_artist"] += 1
                continue
            if not album_artist_various:
                stats["artist_various_only"] += 1
            stats["candidates"] += 1
            sources.append(
                {
                    "path": str(flac_path),
                    "root": str(source_root),
                    "destination": destination,
                    "tags": flac_tags,
                }
            )
    print()

    payload = {
        "version": CACHE_VERSION,
        "sources": sources,
        "mp3_index": mp3_index,
        "mp3_fallback": mp3_fallback,
        "stats": dict(stats),
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")

    albums = {
        (record["root"], normalize(record["tags"]["album"] or Path(record["path"]).parent.name))
        for record in sources
        if "tags" in record
    }
    print(f"Candidate tracks (Artist is Various):        {stats['candidates']}")
    print(f"  of which Album Artist is also Various:     {stats['candidates'] - stats['artist_various_only']}")
    print(f"Distinct albums to resolve:                  {len(albums)}")
    print(f"Already have a real Artist (left alone):     {stats['skipped_real_artist']}")
    print(f"  of which Album Artist is Various:          {stats['album_artist_various_only']}")
    print(f"Unreadable FLAC / MP3:                       {stats['flac_unreadable']} / {stats['mp3_unreadable']}")
    print(f"MP3 index entries:                           {len(mp3_index)}")
    print(f"Scan written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
