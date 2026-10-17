"""Embed each album folder's cover image (folder.jpg or cover.jpg) into its FLAC files as the front cover.

Only FLAC files with no embedded front cover are changed. Report-only by default; --apply writes the art.
Every change is logged, and --restore LOG removes the covers that were added.
"""

import argparse
import csv
import hashlib
import struct
import sys
from datetime import datetime
from pathlib import Path

try:
    from mutagen.flac import FLAC, Picture
except ImportError:
    print("This process requires mutagen. Install it with: python -m pip install mutagen", file=sys.stderr)
    raise


COVER_NAMES = ("folder.jpg", "cover.jpg", "folder.jpeg", "cover.jpeg", "folder.png", "cover.png")
FRONT_COVER = 3


def image_size(data: bytes, mime: str) -> tuple[int, int]:
    if mime == "image/png":
        return struct.unpack(">II", data[16:24])
    index = 2
    while index < len(data) - 9:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        length = struct.unpack(">H", data[index + 2:index + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[index + 5:index + 9])
            return width, height
        index += 2 + length
    return 0, 0


def cover_picture(path: Path) -> Picture:
    data = path.read_bytes()
    mime = "image/png" if path.suffix.casefold() == ".png" else "image/jpeg"
    picture = Picture()
    picture.type = FRONT_COVER
    picture.mime = mime
    picture.desc = "Front Cover"
    picture.data = data
    picture.width, picture.height = image_size(data, mime)
    picture.depth = 24
    return picture


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
            kept = [item for item in audio.pictures if hashlib.md5(item.data).hexdigest() != row["cover_md5"]]
            audio.clear_pictures()
            for item in kept:
                audio.add_picture(item)
            audio.save()
            restored += 1
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, nargs="?", help="Folder to search for album folders")
    parser.add_argument("--cover-map", type=Path, metavar="CSV", help="CSV with folder,image columns choosing the cover for specific folders")
    parser.add_argument("--apply", action="store_true", help="Embed the covers")
    parser.add_argument("--restore", type=Path, metavar="LOG", help="Remove the covers added in a change log")
    args = parser.parse_args()
    here = Path(__file__).parent

    if args.restore:
        print(f"Restored: {restore(args.restore)}")
        return 0
    if not args.root or not args.root.is_dir():
        parser.error("an existing folder is required")

    chosen = {}
    if args.cover_map:
        with args.cover_map.open(newline="", encoding="utf-8") as handle:
            for entry in csv.DictReader(handle):
                folder, image = Path(entry["folder"]), Path(entry["folder"]) / entry["image"]
                if not image.is_file():
                    parser.error(f"cover image does not exist: {image}")
                chosen[folder] = image

    rows = []
    folders = sorted({path.parent for path in args.root.rglob("*.flac")}, key=lambda item: str(item).casefold())
    if chosen:
        folders = [folder for folder in folders if folder in chosen]
    for folder in folders:
        cover = chosen.get(folder) or next((folder / name for name in COVER_NAMES if (folder / name).is_file()), None)
        picture = cover_picture(cover) if cover else None
        for path in sorted(folder.glob("*.flac"), key=lambda item: str(item).casefold()):
            audio = FLAC(path)
            has_front = any(item.type == FRONT_COVER for item in audio.pictures)
            changed = bool(picture) and not has_front
            if changed and args.apply:
                audio.add_picture(picture)
                audio.save()
            rows.append({
                "file": str(path),
                "cover": str(cover or ""),
                "cover_md5": hashlib.md5(picture.data).hexdigest() if picture else "",
                "size": f"{picture.width}x{picture.height}" if picture else "",
                "changed": "yes" if changed else "no",
                "reason": "" if changed else ("already has a front cover" if has_front else "no cover image in folder"),
            })

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = here / (f"embed_cover_art_changes_{stamp}.csv" if args.apply else "embed_cover_art_preview.csv")
    write_csv(log, rows)
    changed = sum(1 for row in rows if row["changed"] == "yes")
    no_cover = sum(1 for row in rows if row["reason"] == "no cover image in folder")
    print(f"Folders: {len(folders)}  Tracks: {len(rows)}  {'Changed' if args.apply else 'Would change'}: {changed}  No cover image: {no_cover}")
    print(f"{'Change log' if args.apply else 'Preview'}: {log}")
    if args.apply:
        print(f"Undo with: --restore \"{log}\"")
    else:
        print("Report only. Re-run with --apply to embed the covers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
