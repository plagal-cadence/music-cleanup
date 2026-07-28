from __future__ import annotations

import argparse
from pathlib import Path
from collections import defaultdict


def find_non_flac_files(root: Path) -> dict[str, int]:
    allowed_ext = {
        ".flac",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".m3u",
    }

    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    root = root.resolve()
    non_flac_counts: dict[str, int] = defaultdict(int)

    for file_path in root.rglob("*"):
        if "$RECYCLE.BIN" in file_path.parts:
            continue
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext not in allowed_ext:
            non_flac_counts[ext] += 1

    return dict(sorted(non_flac_counts.items(), key=lambda x: -x[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Find non-FLAC files by extension.")
    parser.add_argument("--path", default=r"M:\MusicFlacSource", help="Root path to scan")
    args = parser.parse_args()

    root = Path(args.path)

    try:
        non_flac_counts = find_non_flac_files(root)
    except FileNotFoundError as exc:
        print(exc)
        return 1

    print(f"Scanning files under {root} for non-FLAC/non-image files ...\n")

    if not non_flac_counts:
        print("✓ All files are FLAC or allowed image/metadata files!")
    else:
        print("Non-FLAC file types found:")
        for ext, count in non_flac_counts.items():
            print(f"  {ext:20s} : {count:5d} files")
        total = sum(non_flac_counts.values())
        print(f"\n  Total non-FLAC files : {total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
