"""Rewrite the ALBUM tag of FLAC files under a folder using a regular expression and a template.

The pattern's named groups fill the template; groups that are all digits become numbers, so
{disc:02d} zero-pads. Example:
  --pattern "^The Duke Ellington Centennial Edition - CD (?P<disc>\\d+) - (?P<rest>.+)$"
  --template "Duke Ellington Centennial Edition CD {disc:02d} - {rest}"

Report-only by default; --apply writes the tags. Every change is logged, and --restore LOG puts the old names back.
Files whose album does not match the pattern are reported and left unchanged.
"""

import argparse
import csv
import re
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
            if row["changed"] != "yes":
                continue
            audio = FLAC(row["file"])
            audio["album"] = row["old_album"]
            audio.save()
            restored += 1
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, nargs="?", help="Folder to search for FLAC files")
    parser.add_argument("--pattern", help="Regular expression matched against the whole current album name")
    parser.add_argument("--template", help="New album name built from the pattern's named groups")
    parser.add_argument("--apply", action="store_true", help="Write the tags")
    parser.add_argument("--restore", type=Path, metavar="LOG", help="Put back the old album names from a change log")
    args = parser.parse_args()
    here = Path(__file__).parent

    if args.restore:
        print(f"Restored: {restore(args.restore)}")
        return 0
    if not (args.root and args.root.is_dir() and args.pattern and args.template):
        parser.error("an existing folder, --pattern and --template are required")
    pattern = re.compile(args.pattern)

    rows = []
    for path in sorted(args.root.rglob("*.flac"), key=lambda item: str(item).casefold()):
        audio = FLAC(path)
        old = (audio.get("album") or [""])[0]
        match = pattern.fullmatch(old)
        new = old
        if match:
            groups = {key: int(value) if value and value.isdigit() else value for key, value in match.groupdict().items()}
            new = args.template.format(**groups)
        changed = new != old
        if changed and args.apply:
            audio["album"] = new
            audio.save()
        rows.append({"file": str(path), "old_album": old, "new_album": new, "changed": "yes" if changed else "no", "matched": "yes" if match else "no"})

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = here / (f"rename_album_tags_changes_{stamp}.csv" if args.apply else "rename_album_tags_preview.csv")
    write_csv(log, rows)
    changed = sum(1 for row in rows if row["changed"] == "yes")
    unmatched = sum(1 for row in rows if row["matched"] == "no")
    print(f"Tracks: {len(rows)}  {'Changed' if args.apply else 'Would change'}: {changed}  Not matching the pattern: {unmatched}")
    for old, new in sorted({(row["old_album"], row["new_album"]) for row in rows if row["changed"] == "yes"}):
        print(f"  {old}\n    -> {new}")
    print(f"{'Change log' if args.apply else 'Preview'}: {log}")
    if args.apply:
        print(f"Undo with: --restore \"{log}\"")
    else:
        print("Report only. Re-run with --apply to write the tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
