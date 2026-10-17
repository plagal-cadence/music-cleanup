"""Set the Year (FLAC DATE tag) for every track in each album folder listed in a CSV.

The CSV has columns: folder, year, source. Report-only by default; --apply writes the tags.
Every change is logged with the old value, and --restore LOG puts the old values back.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

try:
    from mutagen.flac import FLAC
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def restore(log: Path) -> int:
    restored = 0
    with log.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            audio = FLAC(row["file"])
            if row["old_date"]:
                audio["date"] = row["old_date"].split(" | ")
            elif "date" in audio:
                del audio["date"]
            audio.save()
            restored += 1
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mapping", type=Path, nargs="?", help="CSV with folder,year,source columns")
    parser.add_argument("--apply", action="store_true", help="Write the DATE tags")
    parser.add_argument("--restore", type=Path, metavar="LOG", help="Put back the old DATE values from a change log")
    args = parser.parse_args()
    here = Path(__file__).parent

    if args.restore:
        print(f"Restored: {restore(args.restore)}")
        return 0
    if not args.mapping:
        parser.error("a mapping CSV is required")

    with args.mapping.open(newline="", encoding="utf-8") as handle:
        mapping = list(csv.DictReader(handle))

    rows = []
    for entry in mapping:
        folder, year = Path(entry["folder"]), entry["year"].strip()
        if not folder.is_dir():
            parser.error(f"folder does not exist: {folder}")
        if not (year.isdigit() and len(year) == 4):
            parser.error(f"year must be four digits: {year!r} for {folder}")
        for path in sorted(folder.glob("*.flac"), key=lambda item: str(item).casefold()):
            audio = FLAC(path)
            old = " | ".join(audio.get("date", []))
            changed = old != year
            if changed and args.apply:
                audio["date"] = year
                audio.save()
            rows.append({"file": str(path), "old_date": old, "new_date": year, "changed": "yes" if changed else "no", "source": entry.get("source", "")})

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = here / (f"set_album_year_changes_{stamp}.csv" if args.apply else "set_album_year_preview.csv")
    write_csv(log, rows)
    changed = sum(1 for row in rows if row["changed"] == "yes")
    print(f"Folders: {len(mapping)}  Tracks: {len(rows)}  {'Changed' if args.apply else 'Would change'}: {changed}")
    print(f"{'Change log' if args.apply else 'Preview'}: {log}")
    if args.apply:
        print(f"Undo with: --restore \"{log}\"")
    else:
        print("Report only. Re-run with --apply to write the tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
