from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict


def scan_flac_stats(root: Path, max_depth: int | None = None) -> tuple[int, int, list[Path]]:
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    root = root.resolve()
    dir_state: Dict[Path, dict[str, bool]] = {}

    file_count = 0
    total_bytes = 0

    for file_path in root.rglob("*"):
        if "$RECYCLE.BIN" in file_path.parts:
            continue
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        is_flac = ext == ".flac"
        is_wav = ext == ".wav"
        is_mp3 = ext == ".mp3"

        if is_flac:
            file_count += 1
            total_bytes += file_path.stat().st_size

        # Track directory state
        current = file_path.parent
        while True:
            state = dir_state.setdefault(
                current,
                {"has_flac_or_wav": False, "has_mp3": False},
            )

            if is_flac or is_wav:
                state["has_flac_or_wav"] = True
            if is_mp3:
                state["has_mp3"] = True

            if current == root:
                break
            if root not in current.parents:
                break
            current = current.parent

    candidate_dirs = sorted(
        (
            d
            for d, st in dir_state.items()
            if st["has_flac_or_wav"] and not st["has_mp3"]
        ),
        key=lambda p: (len(str(p)), str(p).lower()),
    )

    highest_level: list[Path] = []
    for candidate in candidate_dirs:
        if any(
            candidate != selected and selected in candidate.parents
            for selected in highest_level
        ):
            continue
        # Filter by max_depth if specified
        if max_depth is not None:
            depth = len(candidate.relative_to(root).parts)
            if depth > max_depth:
                continue
        highest_level.append(candidate)

    highest_level.sort(key=lambda p: p.name.lower())
    return file_count, total_bytes, highest_level


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute FLAC totals and FLAC-only directory roots.")
    parser.add_argument("--path", default=r"M:\\", help="Root path to scan")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum depth of directories to report (1=immediate children only)")
    args = parser.parse_args()

    root = Path(args.path)

    try:
        file_count, total_bytes, highest_level_dirs = scan_flac_stats(root, max_depth=args.max_depth)
    except FileNotFoundError as exc:
        print(exc)
        return 1

    total_mb = total_bytes / (1024 * 1024)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    print(f"Scanning files under {root} ...")
    print()
    print(f"FLAC file count : {file_count}")
    print(f"Total size      : {total_bytes:,.0f} bytes")
    print(f"Total size      : {total_mb:,.2f} MB")
    print(f"Total size      : {total_gb:,.2f} GB")
    print()
    print("Highest-level directories with only FLAC + WAV (no MP3) in their subtrees:")
    if not highest_level_dirs:
        print("  (none found)")
    else:
        for d in highest_level_dirs:
            print(f"  {d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
