"""Put the albums moved out of the MusicFromCDsRuss trees under the right
artist folder and the right root, and move the MP3 tree that never moved.

The move that brought `M:\\MusicFromCDsRussFlac` into `M:\\MusicFlacSource`
grouped albums by the **Artist** tag rather than **Album Artist**, so every
compilation was shredded into one folder per performing artist:
`Time-Life Library of Classical Favorites Disc B` became sixteen folders of one
track each. It also sent the whole `_Classical` subtree into the Secular root.

The layout the albums are put back into is not derived from tags. It is read
from `M:\\MusicFromCDsRussMp3`, which the move never touched and which is
therefore still an intact copy of how the discs were organised: album folder
name -> the subtree and artist folder it belongs under. That matters because the
tags cannot be trusted here. Fourteen Mozart box sets carry
`Album Artist = Various`, and grouping on that would file `Piano Sonatas` as a
compilation; the source tree has them under `Wolfgang Amadeus Mozart`, which is
right. They are reported under "Album Artist worth reviewing" and left alone.

Only `Various Artists` is renamed on the way in, to `Various`, which is what the
destination roots already use.

Dry run by default. `--apply` writes, `--rollback 05-regroup_log.csv --apply`
undoes. As with the other scripts here, pass `--log` a fresh name on later runs
or the first run's undo record is overwritten.
"""

import argparse
import csv
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from roots import ROOT_MAPPINGS
from tags import fuzzy_same, is_various, normalize, progress, read_audio_tags, use_utf8_stdout

RUSS_MP3_TREE = Path(r"M:\MusicFromCDsRussMp3")

# Which root each Russ subtree belongs in. Index into ROOT_MAPPINGS: entry 0 is
# Secular, entry 2 is Classical; the Russ path in each entry names the subtree.
SUBTREE_ROOTS = {
    "_Secular": (ROOT_MAPPINGS[0].flac_sources[0], ROOT_MAPPINGS[0].mp3_destinations[0]),
    "_Classical": (ROOT_MAPPINGS[2].flac_sources[0], ROOT_MAPPINGS[2].mp3_destinations[0]),
}

FLAC_ROOTS = [flac for flac, _ in SUBTREE_ROOTS.values()]
MP3_ROOTS = [mp3 for _, mp3 in SUBTREE_ROOTS.values()]

# Every root a compilation could be sitting in, Christian included -- the Russ
# trees had no Christian subtree, so those two roots take no part in the regroup,
# but they are still spelt to the same convention and worth checking. Roots that
# no longer exist, such as the consumed Russ FLAC tree, are skipped when walked.
ALL_ROOTS = [
    root
    for mapping in ROOT_MAPPINGS
    for root in (*mapping.flac_sources, *mapping.mp3_destinations)
]

# The destination roots spell a compilation's artist folder "Various".
VARIOUS_FOLDER = "Various"

AUDIO_SUFFIXES = {".flac", ".mp3"}

# A folder is accepted as the counterpart of a Russ album when this fraction of
# its tracks fuzzy-match a track in that album. Filenames differ between the two
# trees by more than punctuation -- the MP3s are `01 - Title.mp3` and the FLACs
# `01 Title.flac`, and accents survive in one tree but not always the other --
# so the comparison is on normalized stems and is deliberately not exact.
NAME_MATCH_THRESHOLD = 0.8
COVERAGE_THRESHOLD = 0.7

LOG_FIELDS = ["action", "album", "from", "to", "status", "detail"]


def same_track(left: str, right: str) -> bool:
    """Whether two normalized filename stems name the same track.

    Fuzzy equality catches the accents and typos that differ between the trees
    (`Gymnopedie` / `Gymnopédie`, `Mediaaation` / `Meditation`). Containment
    catches the other habit: the FLAC name often spells out what the MP3 name
    abbreviated, so `02 Elvira Madigan (Piano Concerto No. 21 K.467)` and
    `02 - Elvira Madigan` are the same track on the same disc. Both stems begin
    with the track number, which is what keeps containment from being loose.
    """
    if fuzzy_same(left, right, NAME_MATCH_THRESHOLD):
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 6 and longer.startswith(shorter)


def album_folders(root: Path):
    """Yield (artist_dir, album_dir) for the <root>/<artist>/<album> layout."""
    if not root.exists():
        return
    for artist_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for album_dir in sorted(p for p in artist_dir.iterdir() if p.is_dir()):
            yield artist_dir, album_dir


def audio_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.casefold() in AUDIO_SUFFIXES)


def all_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file())


class Manifest:
    """How the discs were organised, read from the untouched Russ MP3 tree."""

    def __init__(self, tree: Path) -> None:
        self.albums: dict[str, dict] = {}
        self.ambiguous: dict[str, list[str]] = {}
        seen = defaultdict(list)

        for subtree in SUBTREE_ROOTS:
            base = tree / subtree
            if not base.exists():
                continue
            for artist_dir, album_dir in album_folders(base):
                seen[album_dir.name].append(f"{subtree}\\{artist_dir.name}")
                self.albums[album_dir.name] = {
                    "subtree": subtree,
                    "artist": artist_dir.name,
                    "target_artist": (
                        VARIOUS_FOLDER if is_various(artist_dir.name) else artist_dir.name
                    ),
                    "source": album_dir,
                    "stems": [normalize(p.stem) for p in audio_files(album_dir)],
                }

        # One album name under two artists would make the mapping a guess.
        self.ambiguous = {name: places for name, places in seen.items() if len(places) > 1}
        for name in self.ambiguous:
            self.albums.pop(name, None)

    def target(self, album_name: str, *, flac: bool) -> Path:
        entry = self.albums[album_name]
        flac_root, mp3_root = SUBTREE_ROOTS[entry["subtree"]]
        root = flac_root if flac else mp3_root
        return root / entry["target_artist"] / album_name

    def coverage(self, album_name: str, folder: Path) -> tuple[int, int]:
        """How many of this folder's tracks are recognisable in the Russ album."""
        stems = self.albums[album_name]["stems"]
        tracks = audio_files(folder)
        matched = sum(
            1
            for track in tracks
            if any(same_track(normalize(track.stem), stem) for stem in stems)
        )
        return matched, len(tracks)


def plan_regroup(manifest: Manifest, roots: list[Path], *, flac: bool) -> list[dict]:
    """Albums sitting somewhere other than where the Russ tree says they go."""
    plans = []
    for root in roots:
        for artist_dir, album_dir in album_folders(root):
            if album_dir.name not in manifest.albums:
                continue
            target = manifest.target(album_dir.name, flac=flac)
            if album_dir == target:
                continue
            if not audio_files(album_dir):
                continue
            matched, total = manifest.coverage(album_dir.name, album_dir)
            verified = total > 0 and matched / total >= COVERAGE_THRESHOLD
            plans.append(
                {
                    "action": "regroup-flac" if flac else "regroup-mp3",
                    "album": album_dir.name,
                    "source": album_dir,
                    "target": target,
                    "verified": verified,
                    "detail": f"{matched}/{total} tracks recognised",
                }
            )
    return plans


def plan_various_folders(roots: list[Path]) -> list[dict]:
    """Albums filed under a folder that spells Various some other way.

    Independent of the Russ trees: a root that holds both `Various` and
    `Various Artists` splits one artist across two folders for no reason. Only
    names that *are* the word are folded in, which is why `Big Band - Various`
    is left alone -- that is a band name that happens to end in it, not a
    compilation folder.
    """
    plans = []
    for root in roots:
        for artist_dir, album_dir in album_folders(root):
            if artist_dir.name == VARIOUS_FOLDER or not is_various(artist_dir.name):
                continue
            if not audio_files(album_dir):
                continue
            plans.append(
                {
                    "action": "fold-various",
                    "album": album_dir.name,
                    "source": album_dir,
                    "target": root / VARIOUS_FOLDER / album_dir.name,
                    # Nothing to corroborate: same root, same album folder name,
                    # only the artist folder above it is being spelt properly.
                    "verified": True,
                    "detail": f"{artist_dir.name} -> {VARIOUS_FOLDER}",
                }
            )
    return plans


def plan_import(manifest: Manifest) -> list[dict]:
    """The MP3 tree that was never moved at all."""
    plans = []
    for album_name, entry in sorted(manifest.albums.items()):
        source = entry["source"]
        target = manifest.target(album_name, flac=False)
        if source == target:
            continue
        plans.append(
            {
                "action": "import-mp3",
                "album": album_name,
                "source": source,
                "target": target,
                "verified": True,
                "detail": f"{len(entry['stems'])} tracks",
            }
        )
    return plans


class MoveState:
    """What the run has already committed to, so a dry run counts the same.

    Sixteen fragments of one compilation merge into a single folder, so whether
    the seventeenth file collides depends on the sixteen before it. Under
    `--apply` those are on disk and could be read back; in a dry run they are
    not, and reading the target each time would under-report conflicts and
    over-report which folders end up empty. Both modes therefore consult this.
    """

    def __init__(self) -> None:
        self.planned: set[Path] = set()  # paths this run has claimed at a target
        self.leaving: set[Path] = set()  # files this run takes out of a folder
        self._taken: dict[Path, set[str]] = {}

    def taken_at(self, target: Path) -> set[str]:
        if target not in self._taken:
            stems = set()
            if target.exists():
                stems = {normalize(p.stem) for p in audio_files(target)}
            self._taken[target] = stems
        return self._taken[target]

    def would_be_empty(self, folder: Path) -> bool:
        return all(p in self.leaving for p in all_files(folder))


def move_album(plan: dict, *, apply: bool, log: list[dict], state: "MoveState") -> None:
    """Move every file across, refusing to overwrite or duplicate a track.

    The target folder often already exists, because the first fragment of a
    shredded compilation creates it and the other fifteen merge into it. A track
    already present under a name that differs only in punctuation or spacing is
    still the same track, so the comparison is on normalized stems: without that
    the album whose only difference was a collapsed double space would gain a
    second copy of its first track.
    """
    source: Path = plan["source"]
    target: Path = plan["target"]
    taken = state.taken_at(target)

    for file_path in all_files(source):
        relative = file_path.relative_to(source)
        destination = target / relative
        is_audio = file_path.suffix.casefold() in AUDIO_SUFFIXES
        stem = normalize(file_path.stem)

        if destination in state.planned or destination.exists() or (is_audio and stem in taken):
            log.append(
                {
                    "action": plan["action"],
                    "album": plan["album"],
                    "from": str(file_path),
                    "to": str(destination),
                    "status": "conflict",
                    "detail": "a track of this name is already there",
                }
            )
            continue

        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(destination))
        if is_audio:
            taken.add(stem)
        state.planned.add(destination)
        state.leaving.add(file_path)
        log.append(
            {
                "action": plan["action"],
                "album": plan["album"],
                "from": str(file_path),
                "to": str(destination),
                "status": "moved",
                "detail": plan["detail"],
            }
        )


def prune(folder: Path, stop_at: Path, *, apply: bool, log: list[dict], state: MoveState) -> None:
    """Remove folders the move emptied, up to but never including a root."""
    current = folder
    while current != stop_at and stop_at in current.parents:
        if not current.exists():
            break
        if not state.would_be_empty(current):
            break
        if apply:
            if any(current.iterdir()):
                break
            current.rmdir()
        log.append(
            {
                "action": "prune",
                "album": "",
                "from": str(current),
                "to": "",
                "status": "removed",
                "detail": "emptied by the regroup",
            }
        )
        current = current.parent


def report_album_artists(manifest: Manifest) -> None:
    """Albums whose Album Artist says Various where the source tree disagrees.

    Left alone on purpose: these are box sets by one composer that were tagged
    `Various`, so the tag is the thing that is wrong, not the folder.
    """
    print("\n=== Album Artist worth reviewing (nothing moved for these) ===")
    found = 0
    for album_name, entry in sorted(manifest.albums.items()):
        if is_various(entry["artist"]):
            continue
        # Read where the album is now, not where the manifest found it: after an
        # `--apply` the source folder has been moved away, and reading it would
        # make this report go quietly empty on exactly the run that created it.
        folders = [entry["source"], manifest.target(album_name, flac=True)]
        folders.append(manifest.target(album_name, flac=False))
        values = set()
        for folder in folders:
            if not folder.exists():
                continue
            for track in audio_files(folder):
                try:
                    values.add(read_audio_tags(track)["album_artist"])
                except Exception:
                    continue
        if any(is_various(value) for value in values):
            found += 1
            print(f"  {entry['artist']} / {album_name}: Album Artist = {sorted(values)}")
    if not found:
        print("  (none)")


def rollback(log_path: Path, *, apply: bool) -> None:
    rows = list(csv.DictReader(log_path.open(encoding="utf-8-sig")))
    print(f"Rolling back {len(rows)} rows from {log_path.name}{'' if apply else ' (dry run)'}")
    restored = skipped = 0
    for row in reversed(rows):
        if row["status"] != "moved":
            continue
        source = Path(row["from"])
        destination = Path(row["to"])
        if not destination.exists() or source.exists():
            skipped += 1
            continue
        if apply:
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(source))
        restored += 1
    print(f"  {restored} files restored, {skipped} skipped (already back, or gone)")


def main() -> None:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write; otherwise dry run")
    parser.add_argument("--log", default="05-regroup_log.csv", help="where to record the moves")
    parser.add_argument("--rollback", help="undo the moves recorded in this log")
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="regroup what is already in the roots, leave the Russ MP3 tree alone",
    )
    args = parser.parse_args()

    if args.rollback:
        rollback(Path(args.rollback), apply=args.apply)
        return

    manifest = Manifest(RUSS_MP3_TREE)
    print(f"{len(manifest.albums)} albums in the layout read from {RUSS_MP3_TREE}")
    if manifest.ambiguous:
        print(f"{len(manifest.ambiguous)} album names skipped as ambiguous:")
        for name, places in manifest.ambiguous.items():
            print(f"  {name}: {places}")

    plans = plan_regroup(manifest, FLAC_ROOTS, flac=True)
    plans += plan_regroup(manifest, MP3_ROOTS, flac=False)
    plans += plan_various_folders(ALL_ROOTS)
    if not args.skip_import:
        plans += plan_import(manifest)

    unverified = [p for p in plans if not p["verified"]]
    plans = [p for p in plans if p["verified"]]

    if unverified:
        print(f"\n{len(unverified)} folders skipped as unrecognised:")
        for plan in unverified:
            print(f"  {plan['source']}  ({plan['detail']})")

    by_action = defaultdict(list)
    for plan in plans:
        by_action[plan["action"]].append(plan)
    print()
    for action, items in by_action.items():
        albums = len({p["album"] for p in items})
        print(f"{action}: {len(items)} folders covering {albums} albums")

    print(f"\n=== {'moves' if args.apply else 'dry run: what would move'} ===")
    log: list[dict] = []
    state = MoveState()
    for index, plan in enumerate(plans, start=1):
        move_album(plan, apply=args.apply, log=log, state=state)
        progress(index, len(plans), "regrouping")
    print()

    # Prune only after everything has moved, so a folder that fed two different
    # albums is judged on its final state rather than a half-finished one.
    for plan in plans:
        prune(plan["source"], plan["source"].parents[1], apply=args.apply, log=log, state=state)

    moved = sum(1 for row in log if row["status"] == "moved")
    conflicts = [row for row in log if row["status"] == "conflict"]
    pruned = sum(1 for row in log if row["status"] == "removed")

    if conflicts:
        print(f"\n=== {len(conflicts)} files already present at the target ===")
        for row in conflicts:
            print(f"  {row['to']}")
        print("  These were left where they are; nothing was overwritten.")

    log_path = Path(args.log)
    if log:
        with log_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
            writer.writeheader()
            writer.writerows(log)

    print(f"\n{moved} files moved, {len(conflicts)} conflicts, {pruned} folders removed")
    print(f"Log: {log_path}")
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")

    report_album_artists(manifest)

    if args.apply:
        print(
            "\nAlbum folders have moved, so re-run 01-scan.py before the next 02-resolve.py."
        )


if __name__ == "__main__":
    main()
