"""Report-only audit of FLAC album folders before MediaMonkey import.

Per folder with FLAC files: Grouping values, embedded front covers, cover image files,
disc numbering for multi-disc albums, and whole-disc images referenced by .cue files.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

try:
    from mutagen.flac import FLAC
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise

from analyze_and_move_full_albums import DISC_FOLDER, cue_images
from embed_cover_art import COVER_NAMES, FRONT_COVER


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path(r"M:\MusicTrialFlacFull"))
    parser.add_argument("--report", type=Path, help="CSV report path")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"folder does not exist: {args.root}")
    report = args.report or Path(__file__).with_name("audit_trial_albums.csv")

    rows = []
    folders = sorted({path.parent for path in args.root.rglob("*") if path.suffix.casefold() == ".flac"}, key=lambda item: str(item).casefold())
    for folder in folders:
        files = [item for item in folder.iterdir() if item.is_file()]
        images = cue_images(files)
        flacs = sorted((item for item in files if item.suffix.casefold() == ".flac" and item not in images), key=lambda item: str(item).casefold())
        groupings, discs, disc_totals = Counter(), Counter(), Counter()
        embedded = 0
        for path in flacs:
            audio = FLAC(path)
            groupings[" | ".join(audio.get("grouping", [])) or "(none)"] += 1
            discs[(audio.get("discnumber") or [""])[0].split("/")[0]] += 1
            disc_totals[(audio.get("disctotal") or audio.get("totaldiscs") or [""])[0]] += 1
            embedded += any(item.type == FRONT_COVER for item in audio.pictures)
        cover = next((name for name in COVER_NAMES if (folder / name).is_file()), "")
        other_images = sorted(item.name for item in files if item.suffix.casefold() in IMAGE_SUFFIXES and item.name.casefold() not in COVER_NAMES)
        disc_folder = DISC_FOLDER.match(folder.name)
        sibling_discs = [item for item in folder.parent.iterdir() if item.is_dir() and DISC_FOLDER.match(item.name)] if disc_folder else []

        issues = []
        if embedded < len(flacs):
            issues.append("missing embedded cover" + ("; folder has " + cover if cover else "; no folder.jpg/cover.jpg" + ("; other images: " + ", ".join(other_images[:3]) if other_images else "")))
        if disc_folder and (not discs or "" in discs):
            issues.append(f"disc folder ({len(sibling_discs)} discs) without disc numbers")
        if disc_folder and "" in disc_totals:
            issues.append("disc total missing")
        if len(groupings) > 1:
            issues.append("mixed Grouping values")
        if images:
            issues.append("whole-disc image: " + ", ".join(item.name for item in images))
        rows.append({
            "folder": str(folder.relative_to(args.root)),
            "flac_count": len(flacs),
            "grouping": "; ".join(f"{value} ({count})" for value, count in groupings.most_common()),
            "embedded_cover": f"{embedded}/{len(flacs)}",
            "cover_file": cover,
            "other_images": ", ".join(other_images[:5]),
            "disc_numbers": ", ".join(sorted((value or "(none)") for value in discs)),
            "disc_total": ", ".join(sorted((value or "(none)") for value in disc_totals)),
            "disc_image": ", ".join(item.name for item in images),
            "issues": "; ".join(issues),
        })

    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    count = lambda text: sum(1 for row in rows if text in row["issues"])
    print(f"Album folders: {len(rows)}  FLACs: {sum(row['flac_count'] for row in rows)}")
    print(f"With Grouping: {sum(1 for row in rows if '(none)' not in row['grouping'])}  Mixed Grouping: {count('mixed Grouping')}")
    print(f"Missing embedded cover: {count('missing embedded cover')}  (cover file available: {count('folder has')}, none: {count('no folder.jpg')})")
    print(f"Disc folders without disc numbers: {count('without disc numbers')}  Disc total missing: {count('disc total missing')}")
    print(f"Whole-disc images: {count('whole-disc image')}")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
