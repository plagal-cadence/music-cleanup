"""Create track-level FLAC/MP3 tag proposals from album format decisions."""

import argparse
import csv
import importlib.util
import re
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("01-cleanup_various_artists.py")
MODULE_SPEC = importlib.util.spec_from_file_location("cleanup_album_review", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise ImportError(f"Unable to load {MODULE_PATH}")
cleanup = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(cleanup)


VALID_FORMATS = {"Title-Artist", "Artist-Title"}


def filename_artist(file_path: Path, filename_format: str) -> str:
    stem = file_path.stem
    stem = re.sub(r"^\s*\d+(?:[.-]\d+)?\s*-\s*", "", stem).strip()
    if filename_format == "Artist-Title":
        return stem.split("-", 1)[0].strip() if "-" in stem else ""
    return stem.rsplit("-", 1)[-1].strip() if "-" in stem else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=Path(__file__).with_name("01-various_artists_album_review.csv"))
    parser.add_argument("--scan-cache", type=Path, default=Path(__file__).with_name("01-various_artists_scan.json"))
    parser.add_argument("--report", type=Path, default=Path(__file__).with_name("02-various_artists_track_review.csv"))
    parser.add_argument("--log", type=Path, default=Path(__file__).with_name("02-various_artists_track_review.log"))
    args = parser.parse_args()

    with args.review.open(newline="", encoding="utf-8") as handle:
        decisions = list(csv.DictReader(handle))
    decision_map = {}
    invalid = []
    for decision in decisions:
        filename_format = decision["filename_format"].strip()
        if filename_format.casefold() == "none":
            continue
        if filename_format not in VALID_FORMATS:
            invalid.append(f"{decision['source_root']} | {decision['album']}")
            continue
        decision_map[(decision["source_root"], cleanup.normalize(decision["album"]))] = filename_format
    if invalid:
        invalid_details = "\n".join(f"  - {item}" for item in invalid[:10])
        remaining = len(invalid) - min(len(invalid), 10)
        if remaining:
            invalid_details += f"\n  - ... and {remaining} more"
        parser.error(
            "Choose Title-Artist or Artist-Title for every album before running "
            f"({len(invalid)} invalid):\n{invalid_details}"
        )

    for root_mapping in cleanup.ROOT_MAPPINGS:
        for root in (*root_mapping.flac_sources, *root_mapping.mp3_destinations):
            if not root.is_dir():
                parser.error(f"root does not exist or is not a directory: {root}")
    scan = cleanup.load_scan_cache(args.scan_cache, rebuild=False)
    online_cache: dict[str, list[str]] = {}
    rows = []
    for number, record in enumerate(scan["sources"], 1):
        tags = record["tags"]
        album = tags.get("album") or Path(record["path"]).parent.name
        filename_format = decision_map.get((record["root"], cleanup.normalize(album)))
        if not filename_format:
            continue
        cleanup.progress(number, len(scan["sources"]), "Processing selected albums")
        row = cleanup.process_source(record, scan["mp3_index"], online_cache)
        if row is None:
            continue
        flac_path = Path(record["path"])
        parsed_artist = filename_artist(flac_path, filename_format)
        row["filename_format"] = filename_format
        row["filename_artist"] = parsed_artist
        if row["status"] == "would_update" and parsed_artist and not cleanup.fuzzy_same(parsed_artist, row["flac_artist_after"]):
            row["status"] = "review"
            row["details"] = f"filename Artist ({parsed_artist}) differs from MusicBrainz Artist ({row['flac_artist_after']})"
        rows.append(row)
    print()

    fields = [
        "flac_path", "mp3_path", "source_root", "album", "title", "filename_format", "filename_artist",
        "flac_artist_before", "flac_album_artist_before", "flac_artist_after", "flac_album_artist_after",
        "mp3_artist_before", "mp3_album_artist_before", "mp3_artist_after", "mp3_album_artist_after",
        "validated_artists", "status", "details",
    ]
    with args.report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = [
        f"Track rows: {len(rows)}",
        f"Would update both FLAC and MP3: {sum(row['status'] == 'would_update' for row in rows)}",
        f"Needs review: {sum(row['status'] == 'review' for row in rows)}",
        f"Track review report: {args.report}",
    ]
    print("\n".join(summary))
    args.log.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"Run log: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
