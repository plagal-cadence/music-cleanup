"""Bring album folder names, filenames and Album tags into line for the albums
listed in 02-review.md.

Three things are corrected, per album, in both the FLAC source and the MP3 it was
converted into:

* the Album tag, to the value in ALBUM_FIXES
* runs of spaces inside filenames, collapsed to one
* the album folder name, to match the Album tag

Filenames and tags are done before the folder rename so the logged paths stay
valid as the run proceeds, and so a rollback that undoes the folder first finds
the files where the log says they are.

Dry run by default. Nothing is written without --apply.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from roots import ROOT_MAPPINGS
from tags import progress, read_audio_tags, use_utf8_stdout, write_album

AUDIO_SUFFIXES = {".flac", ".mp3"}
RUN_OF_SPACES = re.compile(r" {2,}")


@dataclass(frozen=True)
class AlbumFix:
    """One album: the folder name it has now, and the names it should have."""

    old_folder: str
    new_folder: str
    album: str


def _same_name(fix: AlbumFix) -> AlbumFix:
    """A fix whose Album tag is its corrected folder name."""
    return AlbumFix(fix.old_folder, fix.new_folder, fix.new_folder)


ALBUM_FIXES = [
    # Reader's Digest: two discs of one set, folders named as if unrelated.
    _same_name(AlbumFix(
        "Reader's Digest-100 World's Most Beautiful Melodies",
        "Reader's Digest 100 World's Most Beautiful Melodies (Disc 1)",
        "",
    )),
    _same_name(AlbumFix(
        "Most Beautiful Melodies",
        "Reader's Digest 100 World's Most Beautiful Melodies (Disc 2)",
        "",
    )),
    # Time-Life: a double space after "of" in the folder name and the Album tag.
    *(
        _same_name(AlbumFix(
            f"Time-Life Library of  Classical Favorites - {disc}",
            f"Time-Life Library of Classical Favorites - {disc}",
            "",
        ))
        for disc in (
            "Orchestral Blockbusters Disk A",
            "Orchestral Blockbusters Disk B",
            "Romantic Piano Concertos, Disc 1",
            "Romantic Piano Concertos, Disc 2",
        )
    ),
]


def all_roots() -> list[Path]:
    """Every FLAC source and MP3 destination, in mapping order, deduplicated."""
    roots: list[Path] = []
    for mapping in ROOT_MAPPINGS:
        roots.extend(mapping.flac_sources)
        roots.extend(mapping.mp3_destinations)
    seen: set[Path] = set()
    return [root for root in roots if not (root in seen or seen.add(root))]


def collapse(text: str) -> str:
    return RUN_OF_SPACES.sub(" ", text).strip()


def find_album_folders(roots: list[Path]) -> list[tuple[AlbumFix, Path]]:
    """Locate each album's folder, whether it still has its old name or not.

    Matching both names means a re-run after a partial apply picks up where it
    left off instead of reporting the album as missing.
    """
    wanted = {}
    for fix in ALBUM_FIXES:
        wanted[fix.old_folder.casefold()] = fix
        wanted[fix.new_folder.casefold()] = fix

    found: list[tuple[AlbumFix, Path]] = []
    for root in roots:
        if not root.exists():
            print(f"  root not present, skipped: {root}")
            continue
        for folder in sorted(path for path in root.rglob("*") if path.is_dir()):
            fix = wanted.get(folder.name.casefold())
            if fix is not None:
                found.append((fix, folder))
    return found


def audio_files(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    )


def plan_folder(fix: AlbumFix, folder: Path) -> list[dict[str, str]]:
    """Everything that needs to change in one album folder, in execution order."""
    changes: list[dict[str, str]] = []

    for track in audio_files(folder):
        wanted_name = collapse(track.stem) + track.suffix
        if wanted_name != track.name:
            changes.append({
                "action": "file_rename",
                "path": str(track),
                "old": track.name,
                "new": wanted_name,
            })

        album = read_audio_tags(track)["album"]
        if album != fix.album:
            # The path recorded is the one the rename above will produce, since
            # that is where the file will be when the tag is written.
            changes.append({
                "action": "album_tag",
                "path": str(folder / wanted_name),
                "old": album,
                "new": fix.album,
            })

    if folder.name != fix.new_folder:
        changes.append({
            "action": "folder_rename",
            "path": str(folder),
            "old": folder.name,
            "new": fix.new_folder,
        })
    return changes


def rename_path(path: Path, new_name: str) -> None:
    """Rename within the same parent, refusing to overwrite anything.

    A case-only change is the exception: Windows reports the destination as
    existing because it is the very path being renamed.
    """
    target = path.with_name(new_name)
    if target.exists() and target.resolve() != path.resolve():
        raise FileExistsError(f"target already exists: {target}")
    path.rename(target)


def execute(changes: list[dict[str, str]], log_path: Path) -> tuple[int, int]:
    applied = 0
    failed = 0
    with log_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["action", "path", "old", "new", "status"])
        writer.writeheader()
        for index, change in enumerate(changes, start=1):
            path = Path(change["path"])
            status = "applied"
            try:
                if change["action"] == "album_tag":
                    write_album(path, change["new"])
                else:
                    rename_path(path, change["new"])
                applied += 1
            except Exception as error:  # noqa: BLE001 - one bad file must not stop the run
                status = f"failed: {error}"
                failed += 1
                print(f"\n  {change['action']} failed on {path}: {error}")
            writer.writerow({**change, "status": status})
            handle.flush()
            progress(index, len(changes), "applying")
    print()
    return applied, failed


def rollback(log_path: Path, apply: bool) -> int:
    """Put back what a previous run changed, newest change first."""
    with log_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if row["status"] == "applied"]

    undone = 0
    for row in reversed(rows):
        path = Path(row["path"])
        if row["action"] == "album_tag":
            target, old_value, new_value = path, row["new"], row["old"]
        else:
            # The forward run renamed path -> new, so the file now sitting there
            # is what has to be renamed back.
            target = path.with_name(row["new"])
            old_value, new_value = row["new"], row["old"]

        print(f"  {row['action']}: {old_value!r} -> {new_value!r}")
        if apply:
            try:
                if row["action"] == "album_tag":
                    write_album(target, new_value)
                else:
                    rename_path(target, new_value)
                undone += 1
            except Exception as error:  # noqa: BLE001
                print(f"    failed: {error}")
        else:
            undone += 1

    print(f"\n{'Undid' if apply else 'Would undo'} {undone} of {len(rows)} changes.")
    return 0


def main() -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually rename and write tags")
    parser.add_argument("--log", type=Path, default=Path(__file__).with_name("04-rename_log.csv"))
    parser.add_argument("--rollback", type=Path, help="Undo a previous run from its log")
    args = parser.parse_args()

    if args.rollback:
        if not args.rollback.exists():
            print(f"No such log: {args.rollback}", file=sys.stderr)
            return 1
        return rollback(args.rollback, args.apply)

    print(f"Looking for {len(ALBUM_FIXES)} albums across {len(all_roots())} roots.")
    found = find_album_folders(all_roots())

    located = {fix.new_folder for fix, _ in found}
    for fix in ALBUM_FIXES:
        if fix.new_folder not in located:
            print(f"  NOT FOUND in any root: {fix.old_folder!r}")

    changes: list[dict[str, str]] = []
    for fix, folder in found:
        folder_changes = plan_folder(fix, folder)
        counts = {
            action: sum(1 for change in folder_changes if change["action"] == action)
            for action in ("file_rename", "album_tag", "folder_rename")
        }
        state = ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        print(f"\n{folder}")
        print(f"  {state or 'already correct'}")
        for change in folder_changes:
            if change["action"] != "album_tag":
                print(f"    {change['action']}: {change['old']!r} -> {change['new']!r}")
        if counts["album_tag"]:
            example = next(c for c in folder_changes if c["action"] == "album_tag")
            print(f"    album_tag x{counts['album_tag']}: "
                  f"{example['old']!r} -> {example['new']!r}")
        changes.extend(folder_changes)

    print(f"\n{len(changes)} changes across {len(found)} folders.")
    if not changes:
        print("Nothing to do.")
        return 0
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
        return 0

    applied, failed = execute(changes, args.log)
    print(f"Applied {applied}, failed {failed}. Log: {args.log}")
    print(f"Undo with: 04-rename.py --rollback {args.log.name} --apply")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
