"""Expand missing-track candidates into track-level path-node analysis."""

from __future__ import annotations

import csv
import re
from pathlib import Path, PureWindowsPath


WORKSPACE = Path(__file__).resolve().parent
INPUT_CSV = WORKSPACE / "03-missing-track-report.csv"
OUTPUT_CSV = WORKSPACE / "06-track-analysis.csv"
CANDIDATE_PATTERN = re.compile(r"(?P<score>\d+(?:\.\d+)?):(?P<path>.*?)(?=;\s*\d+(?:\.\d+)?:|$)")
ROOT_MAPPINGS = (
    (
        r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac",
        r"M:\Music\Christian\MusicFromCDsFromFlac",
    ),
    (
        r"M:\MusicFlacSource\Classical\MusicFromCDs",
        r"M:\Music\Classical\MusicFromCDsFromFlac",
    ),
    (
        r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac",
        r"M:\Music\Secular\MusicFromCDsFromFlac",
    ),
    (
        r"M:\MusicFromCDsRussFlac\_Classical",
        r"M:\MusicFromCDsRussMp3\_Classical",
    ),
    (
        r"M:\MusicFromCDsRussFlac\_Secular",
        r"M:\MusicFromCDsRussMp3\_Secular",
    ),
)


def split_candidate_paths(candidate_text: str) -> list[tuple[float, str]]:
    return [
        (float(match.group("score")), match.group("path").strip())
        for match in CANDIDATE_PATTERN.finditer(candidate_text or "")
    ]


def split_path(path_text: str) -> tuple[str, str]:
    if not path_text:
        return "", ""
    path = PureWindowsPath(path_text)
    return str(path.parent), path.stem


def root_mapping(path_text: str) -> tuple[str, str]:
    normalized_path = path_text.casefold().rstrip("\\/")
    for flac_root, mp3_root in ROOT_MAPPINGS:
        normalized_flac_root = flac_root.casefold().rstrip("\\/")
        if normalized_path == normalized_flac_root or normalized_path.startswith(normalized_flac_root + "\\"):
            return flac_root, mp3_root
    return "", ""


def candidate_root(path_text: str, expected_root: str) -> str:
    normalized_path = path_text.casefold().rstrip("\\/")
    for _, mp3_root in ROOT_MAPPINGS:
        normalized_mp3_root = mp3_root.casefold().rstrip("\\/")
        if normalized_path == normalized_mp3_root or normalized_path.startswith(normalized_mp3_root + "\\"):
            return mp3_root
    return ""


def classify_issue(
    flac_path: str,
    flac_filename_prefix: str,
    candidate_path: str,
    candidate_filename_prefix: str,
) -> str:
    if not candidate_path and not candidate_filename_prefix:
        return "no candidate"

    same_album_name = PureWindowsPath(flac_path).name == PureWindowsPath(candidate_path).name
    same_filename = flac_filename_prefix == candidate_filename_prefix

    if same_album_name and not same_filename:
        return "filename difference"
    if not same_album_name and same_filename:
        return "path/name difference"
    if not same_album_name and not same_filename:
        return "filename and path/name difference"
    return "unclassified"


def main() -> int:
    with INPUT_CSV.open(newline="", encoding="utf-8") as input_file:
        rows = list(csv.DictReader(input_file))

    analysis_rows = []
    for row in rows:
        flac_album = row["flac_album"]
        flac_track = row["flac_track"]
        flac_path, flac_filename_prefix = split_path(
            str(PureWindowsPath(flac_album) / flac_track)
        )
        flac_root, expected_mp3_root = root_mapping(flac_path)

        candidates = split_candidate_paths(row["mp3_path_or_candidates"])[:1]
        if not candidates:
            candidates = [(None, "")]
        for rank, (score, candidate_path) in enumerate(candidates, start=1):
            candidate_directory, candidate_filename_prefix = split_path(candidate_path)
            actual_mp3_root = candidate_root(candidate_directory, expected_mp3_root)
            if not candidate_path:
                root_mapping_issue = "no candidate"
            elif not actual_mp3_root:
                root_mapping_issue = "candidate root not recognized"
            elif actual_mp3_root.casefold() != expected_mp3_root.casefold():
                root_mapping_issue = "unexpected MP3 root"
            else:
                root_mapping_issue = "expected MP3 root"
            analysis_rows.append(
                {
                    "flac_root": flac_root,
                    "expected_mp3_root": expected_mp3_root,
                    "candidate_mp3_root": actual_mp3_root,
                    "root_mapping_issue": root_mapping_issue,
                    "flac_path": flac_path,
                    "flac_filename_prefix": flac_filename_prefix,
                    "mp3_found": row["mp3_found"],
                    "candidate_rank": rank if candidate_path else "",
                    "candidate_score": f"{score:.3f}" if score is not None else "",
                    "candidate_path": candidate_directory,
                    "candidate_filename_prefix": candidate_filename_prefix,
                    "issue": classify_issue(
                        flac_path,
                        flac_filename_prefix,
                        candidate_directory,
                        candidate_filename_prefix,
                    ),
                }
            )

    fieldnames = [
        "flac_root",
        "expected_mp3_root",
        "candidate_mp3_root",
        "root_mapping_issue",
        "flac_path",
        "flac_filename_prefix",
        "mp3_found",
        "candidate_rank",
        "candidate_score",
        "candidate_path",
        "candidate_filename_prefix",
        "issue",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for analysis_row in analysis_rows:
            output_row = {
                key: analysis_row[key]
                for key in fieldnames
                if key in analysis_row
            }
            writer.writerow(output_row)

    print(f"Analyzed tracks: {len(rows)}")
    print(f"Candidate rows: {len(analysis_rows)}")
    print(f"Wrote {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
