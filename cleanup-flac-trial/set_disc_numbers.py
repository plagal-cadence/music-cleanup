"""Set DISCNUMBER and DISCTOTAL on FLAC files from disc folder names (CD01, Disc 2, ...) under a box-set folder.

Report-only by default; --apply writes the tags. Every change is logged with the old values,
and --restore LOG puts them back.
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


DISC_FOLDER = re.compile(r"^(?:cd|disc|disk)\s*[-_.]?\s*(\d+)\b", re.IGNORECASE)
TAGS = ("discnumber", "disctotal", "totaldiscs")


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
            for tag in TAGS:
                old = row[f"old_{tag}"]
                if old:
                    audio[tag] = old.split(" | ")
                elif tag in audio:
                    del audio[tag]
            audio.save()
            restored += 1
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("box_folders", type=Path, nargs="*", help="Folders that contain the disc folders")
    parser.add_argument("--apply", action="store_true", help="Write the tags")
    parser.add_argument("--restore", type=Path, metavar="LOG", help="Put back the old values from a change log")
    args = parser.parse_args()
    here = Path(__file__).parent

    if args.restore:
        print(f"Restored: {restore(args.restore)}")
        return 0
    if not args.box_folders:
        parser.error("at least one box-set folder is required")

    # Validate every box first so a bad folder stops the run before anything is written.
    boxes, problems = [], []
    for box in args.box_folders:
        if not box.is_dir():
            problems.append(f"not a folder: {box}")
            continue
        discs = {}
        for folder in sorted(item for item in box.iterdir() if item.is_dir()):
            match = DISC_FOLDER.match(folder.name)
            if match:
                number = int(match.group(1))
                if number in discs:
                    problems.append(f"{box}: disc {number} appears twice: {discs[number].name} and {folder.name}")
                discs[number] = folder
        if not discs:
            problems.append(f"{box}: no disc folders (CD01, Disc 2, ...)")
        elif sorted(discs) != list(range(1, len(discs) + 1)):
            problems.append(f"{box}: disc folders are not numbered 1..{len(discs)}: {sorted(discs)}")
        boxes.append(discs)
    if problems:
        parser.error("\n  " + "\n  ".join(problems))

    rows = []
    for discs in boxes:
        total = len(discs)
        for number, folder in sorted(discs.items()):
            for path in sorted(folder.glob("*.flac"), key=lambda item: str(item).casefold()):
                audio = FLAC(path)
                old = {tag: " | ".join(audio.get(tag, [])) for tag in TAGS}
                changed = old["discnumber"] != str(number) or old["disctotal"] != str(total) or bool(old["totaldiscs"])
                if changed and args.apply:
                    audio["discnumber"] = str(number)
                    audio["disctotal"] = str(total)
                    if "totaldiscs" in audio:
                        del audio["totaldiscs"]
                    audio.save()
                rows.append({
                    "file": str(path),
                    **{f"old_{tag}": value for tag, value in old.items()},
                    "new_discnumber": number,
                    "new_disctotal": total,
                    "changed": "yes" if changed else "no",
                })

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = here / (f"set_disc_numbers_changes_{stamp}.csv" if args.apply else "set_disc_numbers_preview.csv")
    write_csv(log, rows)
    changed = sum(1 for row in rows if row["changed"] == "yes")
    print(f"Albums: {len(boxes)}  Discs: {sum(len(discs) for discs in boxes)}  Tracks: {len(rows)}  {'Changed' if args.apply else 'Would change'}: {changed}")
    print(f"{'Change log' if args.apply else 'Preview'}: {log}")
    if args.apply:
        print(f"Undo with: --restore \"{log}\"")
    else:
        print("Report only. Re-run with --apply to write the tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
