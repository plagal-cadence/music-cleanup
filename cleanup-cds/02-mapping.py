"""Map FLAC albums to MP3 counterparts and fuzzy-match missing tracks.

Usage: python 02-mapping.py [--mp3-root ROOT] [--top N]

The script extracts `FOLDERS` from 01-inventory.py (without executing it),
locates album directories containing .flac files, then searches for likely
corresponding MP3 album folders and MP3 files. For missing MP3 tracks a
small fuzzy-search (difflib) produces candidate matches.
"""
from __future__ import annotations

import argparse
import ast
import csv
import os
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Tuple


def extract_folders_from_list_albums(path: str) -> List[str]:
    """Return the FOLDERS list value from the given 01-inventory.py file.
    Uses ast to avoid executing that module.
    """
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == "FOLDERS":
                    return ast.literal_eval(node.value)
    return []


def find_album_dirs(flac_roots: Iterable[str]) -> List[str]:
    albums = []
    for root in flac_roots:
        if not os.path.exists(root):
            continue
        for artist_entry in sorted((e for e in os.scandir(root) if e.is_dir()), key=lambda e: e.name):
            # album dirs under artist
            album_dirs = sorted((e for e in os.scandir(artist_entry.path) if e.is_dir()), key=lambda e: e.name)
            if album_dirs:
                for album_entry in album_dirs:
                    # include only if contains flac files
                    if any(f.name.lower().endswith(".flac") for f in os.scandir(album_entry.path) if f.is_file()):
                        albums.append(album_entry.path)
            else:
                # artist folder may directly contain flac files (single-album artist)
                if any(f.name.lower().endswith(".flac") for f in os.scandir(artist_entry.path) if f.is_file()):
                    albums.append(artist_entry.path)
    return albums


def build_mp3_index(mp3_roots: Iterable[str]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Return two indexes:
    - album_dirs_by_tail: map of last path component(s) -> album dir paths
    - files_by_basename: map of filename (lower) -> list of full paths
    """
    album_dirs_by_tail = defaultdict(list)
    files_by_basename = defaultdict(list)
    for root in mp3_roots:
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            mp3_files = [f for f in filenames if f.lower().endswith(".mp3")]
            if mp3_files:
                tail = os.path.basename(dirpath)
                album_dirs_by_tail[tail.lower()].append(dirpath)
                # also try last two components if available
                parent = os.path.basename(os.path.dirname(dirpath))
                if parent:
                    album_dirs_by_tail[f"{parent.lower()}||{tail.lower()}"].append(dirpath)
                for f in mp3_files:
                    files_by_basename[f.lower()].append(os.path.join(dirpath, f))
    return album_dirs_by_tail, files_by_basename


def find_best_mp3_album_candidate(flac_album: str, mp3_album_index: Dict[str, List[str]]) -> List[str]:
    """Try to locate MP3 album directory candidates for the given FLAC album path."""
    tail = os.path.basename(flac_album).lower()
    parent = os.path.basename(os.path.dirname(flac_album)).lower()
    candidates = []
    # exact matches on album tail
    candidates.extend(mp3_album_index.get(tail, []))
    # try parent||tail
    key = f"{parent}||{tail}"
    candidates.extend(mp3_album_index.get(key, []))
    # also try matching by parent only (artist-level)
    candidates.extend(mp3_album_index.get(parent, []))
    # unique
    return list(dict.fromkeys(candidates))


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_find_mp3_for_flac(flac_basename: str, files_index: Dict[str, List[str]], top: int = 3) -> List[Tuple[float, str]]:
    """Return top candidate MP3 paths with similarity score to the FLAC basename (without ext)."""
    flac_key = os.path.splitext(flac_basename)[0].lower()
    # first quick exact-stem match
    exact_matches = []
    for mp3_basename, paths in files_index.items():
        if os.path.splitext(mp3_basename)[0] == flac_key:
            for p in paths:
                exact_matches.append((1.0, p))
            if exact_matches:
                return sorted(exact_matches, key=lambda x: -x[0])[:top]

    # otherwise compute similarity on basename stems
    scores = []
    for mp3_basename, paths in files_index.items():
        stem = os.path.splitext(mp3_basename)[0]
        score = similar(flac_key, stem)
        if score > 0.4:
            for p in paths:
                scores.append((score, p))
    scores.sort(key=lambda x: -x[0])
    return scores[:top]


def main():
    p = argparse.ArgumentParser(description="Map FLAC albums to MP3 and fuzzy-find missing tracks")
    p.add_argument("--list-albums", default=os.path.join(os.path.dirname(__file__), "01-inventory.py"), help="Path to 01-inventory.py to extract FOLDERS")
    p.add_argument("--mp3-root", action="append", help="MP3 root(s) to search (can be specified multiple times). If omitted, the script will attempt plausible siblings of FLAC roots.")
    p.add_argument("--top", type=int, default=3, help="Number of fuzzy candidates to return per missing track")
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "02-mapping.csv"), help="CSV output report path")
    args = p.parse_args()

    flac_roots = extract_folders_from_list_albums(args.list_albums)
    if not flac_roots:
        print("No FOLDERS found in 01-inventory.py")
        return

    flac_albums = find_album_dirs(flac_roots)
    print(f"Found {len(flac_albums)} FLAC album directories to inspect")

    mp3_roots = args.mp3_root or []
    if not mp3_roots:
        # generate plausible mp3 root candidates by simple string replacements
        for r in flac_roots:
            r1 = r.replace("Flac", "Mp3").replace("FLAC", "MP3").replace("flac", "mp3")
            parent = os.path.dirname(r)
            # also check parent for directories containing 'mp3'
            mp3_siblings = [os.path.join(parent, d) for d in os.listdir(parent) if "mp3" in d.lower()] if os.path.exists(parent) else []
            mp3_roots.extend([r1] + mp3_siblings)
        # deduplicate and only keep existing
        mp3_roots = [os.path.normpath(x) for x in dict.fromkeys(mp3_roots) if os.path.exists(x)]

    if not mp3_roots:
        print("No MP3 roots provided or discovered; pass --mp3-root to specify where MP3s live")

    print(f"Using {len(mp3_roots)} MP3 root(s)")

    album_index, files_index = build_mp3_index(mp3_roots)

    # Report rows: flac_album, flac_track, mp3_found(bool), mp3_path_or_candidates
    rows = [("flac_album", "flac_track", "mp3_found", "mp3_path_or_candidates")]

    for album in flac_albums:
        mp3_candidates = find_best_mp3_album_candidate(album, album_index)
        # gather mp3 files in candidate album dirs
        mp3_files_in_album = {}
        for c in mp3_candidates:
            for entry in os.scandir(c):
                if entry.is_file() and entry.name.lower().endswith(".mp3"):
                    mp3_files_in_album[entry.name.lower()] = entry.path

        for f in sorted((e for e in os.scandir(album) if e.is_file() and e.name.lower().endswith(".flac")), key=lambda e: e.name):
            flac_name = f.name
            stem = os.path.splitext(flac_name)[0].lower()
            expected_mp3 = None
            # check direct name match in candidate album dirs
            for cand_name, cand_path in mp3_files_in_album.items():
                if os.path.splitext(cand_name)[0] == stem:
                    expected_mp3 = cand_path
                    break

            if expected_mp3:
                rows.append((album, flac_name, "yes", expected_mp3))
            else:
                # fuzzy search across all mp3 files index
                candidates = fuzzy_find_mp3_for_flac(flac_name, files_index, top=args.top)
                if candidates:
                    cand_str = "; ".join([f"{s:.3f}:{p}" for s, p in candidates])
                else:
                    cand_str = ""
                rows.append((album, flac_name, "no", cand_str))

    # write CSV
    with open(args.out, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        for r in rows:
            writer.writerow(r)

    print(f"Report written to: {args.out}")


if __name__ == "__main__":
    main()
