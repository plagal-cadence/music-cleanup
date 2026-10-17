"""Write approved Artist and Title tags to the FLAC sources and their matching MP3s.

Both values are taken verbatim from the proposals sheet, so editing the `title`
column there is how a title gets corrected. Dry run unless --apply is passed.
Album Artist is never touched: on a compilation it is correctly "Various". Every
write is recorded in an undo log so a run can be reversed with --rollback.
"""

import argparse
import csv
import re
from pathlib import Path

from tags import (
    fuzzy_same,
    is_various,
    normalize,
    progress,
    read_audio_tags,
    use_utf8_stdout,
    write_tags,
)

# Values accepted in the `apply` column. "retitled" means "I rewrote this title on
# purpose", which grants that row the two things a rewritten title needs and
# nothing else: the stale-CSV guard is waived, and the Title is written even where
# the Artist is already correct. Both are otherwise only available as run-wide
# flags, which would apply them to every other row too.
MISMATCH_OK = {"retitled", "retitle"}
APPROVED = {"yes", "y", "true", "1", "apply"} | MISMATCH_OK
LOG_FIELDS = [
    "file", "kind", "artist_before", "artist_after", "title_before", "title_after",
    "album", "status", "detail",
]
SPACE_RUN = re.compile(r"  +")


def decode_sheet(raw: bytes, path: Path) -> str:
    """Decode a sheet Excel may have exported in any of its formats.

    Excel offers four CSV flavours and only one is UTF-8. The others differ in
    both encoding and delimiter, and guessing wrong is quiet rather than loud:
    "Text (Tab delimited)" swaps commas for tabs, giving one giant column and so
    nothing approved to write, while plain "CSV" (Windows-1252) and "CSV
    (MS-DOS)" (OEM) disagree about the bytes below 0xA0. In OEM, 0x84 is the a
    of Jarvi; in cp1252 it is a stray low quote. Both decode without error, so
    the choice is made on which result looks like text: real metadata yields
    accented *letters*, a wrong guess yields scattered punctuation.

    Excel 2013 has no "CSV UTF-8" at all, so its only lossless export is "Unicode
    Text (*.txt)": UTF-16 with a byte-order mark, tab separated. That BOM makes it
    unambiguous, and the delimiter sniff in read_csv covers the tabs.
    """
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    best, best_score = None, None
    for encoding in ("cp1252", "oem", "cp850"):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        exotic = [character for character in text if ord(character) > 127]
        letters = sum(1 for character in exotic if character.isalpha())
        score = letters - 2 * (len(exotic) - letters)
        if best_score is None or score > best_score:
            best, best_score = text, score
    if best is None:
        raise ValueError(f"cannot decode {path} as UTF-8, Windows-1252 or OEM")
    return best


def newest_proposals() -> Path | None:
    """Pick whichever sheet was saved last.

    Excel 2013 cannot write UTF-8 CSV, so a lossless save has to go out as
    "Unicode Text (*.txt)" under a different extension. Following the newer file
    means that save needs no extra flag, and the chosen name is printed so an
    edit that went to the other one is obvious.
    """
    candidates = [
        path
        for suffix in (".csv", ".txt")
        if (path := Path(__file__).with_name(f"02-artist_proposals{suffix}")).exists()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def read_csv(path: Path) -> list[dict]:
    """Read the proposals sheet, whatever encoding and delimiter Excel left."""
    text = decode_sheet(path.read_bytes(), path)
    header = text.splitlines()[0] if text else ""
    delimiter = max(",\t;", key=header.count)
    return list(csv.DictReader(text.splitlines(True), delimiter=delimiter))


def approved(row: dict, include_medium: bool) -> bool:
    if not row.get("proposed_artist", "").strip():
        return False
    flag = row.get("apply", "").strip().casefold()
    if flag in APPROVED:
        return True
    return include_medium and not flag and row.get("confidence") == "medium"


def mismatch_waived(row: dict) -> bool:
    return row.get("apply", "").strip().casefold() in MISMATCH_OK


def title_done(on_disk: str, from_csv: str) -> bool:
    """Does the title on disk already say what the sheet means to write?

    Compared on the normalised form, so a difference of punctuation or case is not
    worth a rewrite. Runs of spaces are the exception: normalising drops
    whitespace entirely, which made `Pomp and Circumstance   March No. 1` count as
    already correct against the single-spaced title meant to replace it, and left
    the only defect the sheet was fixing unfixable. A run of spaces is never
    deliberate, so a difference in one counts as a real difference.
    """
    if normalize(on_disk) != normalize(from_csv):
        return False
    return bool(SPACE_RUN.search(on_disk)) == bool(SPACE_RUN.search(from_csv))


def same_track(on_disk: str, from_csv: str) -> bool:
    """Do these two titles describe the same track?

    Not a test for equality, because the CSV title is now the corrected value we
    intend to write, and a correction usually means dropping the artist credit
    from the title. So a near match counts (an MP3 matched by name similarity may
    already spell the title its FLAC gets wrong) and so does one title being
    contained in the other ("We All Bow Down" inside "Twila Paris - We All Bow
    Down"). An unrelated track still fails both.
    """
    if fuzzy_same(on_disk, from_csv):
        return True
    left, right = normalize(on_disk), normalize(from_csv)
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 6 and shorter in longer


def check_target(path: Path, row: dict, force: bool, retitle: bool,
                 ignore_mismatch: bool = False) -> tuple[dict, str, str]:
    """Return (tags on disk, status, detail). Status 'ok' means safe to write."""
    if not path.exists():
        return {}, "missing", "file no longer exists"
    try:
        current = read_audio_tags(path)
    except (OSError, ValueError, TypeError) as error:
        return {}, "unreadable", str(error)
    artist, csv_title = current["artist"], row.get("title", "").strip()
    artist_done = normalize(artist) == normalize(row["proposed_artist"])
    title_ok = not csv_title or title_done(current["title"], csv_title)
    if artist_done and title_ok:
        return current, "already_set", "Artist and Title already hold the proposed values"
    if artist_done and not retitle:
        # An earlier run already fixed the Artist here, so this track is not part
        # of the current batch. Leave its Title alone unless asked to sweep.
        return current, "already_set", "Artist already correct; Title untouched (pass --retitle to update it)"
    # Only a *different* artist is worth protecting. Where the one on disk already
    # matches the proposal, this row is a title-only correction and overwrites
    # nothing, so demanding --force would just block it for no reason.
    if not artist_done and not is_various(artist) and not force:
        return current, "changed", f"Artist is now {artist!r}, not Various; pass --force to overwrite"
    # Guard against a stale CSV pointing at a different track. Retitling by hand
    # can legitimately trip it ("Overture 1" -> "Nutcracker: Overture" shares
    # almost nothing), so it can be waived - but per row, via apply=retitled,
    # because waiving it for a whole run also waives it for every misaligned row
    # the guard was catching.
    if (csv_title and current["title"] and not ignore_mismatch
            and not same_track(current["title"], csv_title)):
        return current, "mismatch", f"title on disk is {current['title']!r}, expected {csv_title!r}"
    return current, "ok", ""


def rollback(log_path: Path, apply_changes: bool) -> int:
    use_utf8_stdout()
    entries = [row for row in read_csv(log_path) if row["status"] == "written"]
    print(f"Restoring {len(entries)} files from {log_path.name}")
    restored = failed = 0
    for number, entry in enumerate(entries, 1):
        progress(number, len(entries), "Rolling back")
        path = Path(entry["file"])
        # Restore only the fields this run actually changed. Logs from before
        # titles were written carry no title columns at all, so .get() leaves
        # those titles alone.
        artist = entry["artist_before"] if entry["artist_after"] != entry["artist_before"] else None
        title = (
            entry["title_before"]
            if entry.get("title_after", "") != entry.get("title_before", "")
            else None
        )
        try:
            if apply_changes:
                write_tags(path, artist=artist, title=title)
            restored += 1
        except (OSError, ValueError, TypeError) as error:
            failed += 1
            print(f"\n  failed: {path} ({error})")
    print()
    verb = "Restored" if apply_changes else "Would restore"
    print(f"{verb} {restored} files, {failed} failures")
    if not apply_changes:
        print("This was a dry run. Add --apply to write the original values back.")
    return 0


def main() -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", type=Path, help="Defaults to the newer of 02-artist_proposals.csv / .txt")
    parser.add_argument("--log", type=Path, default=Path(__file__).with_name("03-apply_log.csv"))
    parser.add_argument("--apply", action="store_true", help="Actually write tags")
    parser.add_argument("--include-medium", action="store_true",
                        help="Also apply medium-confidence rows you left blank")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite even where Artist is no longer Various")
    parser.add_argument("--retitle", action="store_true",
                        help="Correct Title on EVERY row whose Artist an earlier run already fixed; "
                             "prefer apply=retitled on the individual rows you rewrote")
    parser.add_argument("--ignore-title-mismatch", action="store_true",
                        help="Waive the title guard for EVERY row; prefer apply=retitled on the "
                             "individual rows you rewrote")
    parser.add_argument("--rollback", type=Path, help="Undo a previous run from its log")
    args = parser.parse_args()

    if args.rollback:
        return rollback(args.rollback, args.apply)

    proposals = args.proposals or newest_proposals()
    if proposals is None or not proposals.exists():
        parser.error("proposals not found, run 02-resolve.py first")
    print(f"Sheet: {proposals.name}")
    rows = read_csv(proposals)

    selected = [row for row in rows if approved(row, args.include_medium)]
    print(f"Proposals: {len(rows)}   approved for writing: {len(selected)}")
    waived = sum(1 for row in selected if mismatch_waived(row))
    if args.ignore_title_mismatch:
        print(f"Title guard waived on ALL {len(selected)} approved rows (--ignore-title-mismatch)")
    elif waived:
        print(f"Title guard waived on {waived} rows marked apply=retitled")
    if not selected:
        print("Nothing approved. Put 'yes' in the apply column, or pass --include-medium.")
        return 0

    log_rows = []
    for number, row in enumerate(selected, 1):
        progress(number, len(selected), "Applying artists" if args.apply else "Checking (dry run)")
        artist = row["proposed_artist"].strip()
        title = row.get("title", "").strip()
        for kind, key in (("flac", "flac_path"), ("mp3", "mp3_path")):
            raw = row.get(key, "").strip()
            if not raw:
                continue
            path = Path(raw)
            waive = args.ignore_title_mismatch or mismatch_waived(row)
            current, status, detail = check_target(
                path, row, args.force, args.retitle or mismatch_waived(row), waive
            )
            before_artist, before_title = current.get("artist", ""), current.get("title", "")
            # Only pass a field that actually differs, so a title fix does not
            # rewrite an artist that is already byte-identical.
            new_artist = artist if status == "ok" and artist != before_artist else None
            new_title = title if status == "ok" and title and title != before_title else None
            if status == "ok":
                if new_artist is None and new_title is None:
                    status, detail = "already_set", "both values already exact"
                elif args.apply:
                    try:
                        write_tags(path, artist=new_artist, title=new_title)
                        status = "written"
                    except (OSError, ValueError, TypeError) as error:
                        status, detail = "failed", str(error)
                else:
                    status, detail = "would_write", ""
            done = status in {"written", "would_write"}
            log_rows.append(
                {
                    "file": str(path),
                    "kind": kind,
                    "artist_before": before_artist,
                    "artist_after": new_artist if done and new_artist else before_artist,
                    "title_before": before_title,
                    "title_after": new_title if done and new_title else before_title,
                    "album": row.get("album", ""),
                    "status": status,
                    "detail": detail,
                }
            )
    print()

    log_path = args.log
    try:
        handle = log_path.open("w", newline="", encoding="utf-8-sig")
    except PermissionError:
        log_path = log_path.with_name(f"{log_path.stem}_rerun{log_path.suffix}")
        handle = log_path.open("w", newline="", encoding="utf-8-sig")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(log_rows)

    flac_count = sum(1 for row in log_rows if row["kind"] == "flac" and row["status"] in {"written", "would_write"})
    mp3_count = sum(1 for row in log_rows if row["kind"] == "mp3" and row["status"] in {"written", "would_write"})
    written = [row for row in log_rows if row["status"] in {"written", "would_write"}]
    verb = "Wrote" if args.apply else "Would write"
    print(f"{verb} {flac_count} FLAC and {mp3_count} MP3 files")
    print(f"  Artist changes            {sum(1 for row in written if row['artist_after'] != row['artist_before'])}")
    print(f"  Title changes             {sum(1 for row in written if row['title_after'] != row['title_before'])}")
    for status in sorted({row["status"] for row in log_rows}):
        if status not in {"written", "would_write"}:
            print(f"  {status}: {sum(1 for row in log_rows if row['status'] == status)}")
    print(f"Log: {log_path}")
    if args.apply:
        print(f"To undo: python 03-apply.py --rollback {log_path.name} --apply")
    else:
        print("This was a dry run. Add --apply to write the tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
