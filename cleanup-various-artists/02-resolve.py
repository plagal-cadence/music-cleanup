"""Propose a real Artist for every Various-tagged track, using Spotify to decide.

For each album this picks the title pattern that best explains the tracks, by
asking Spotify whether the extracted candidates are actually artists. A pattern
only wins if it clearly beats the alternatives, otherwise the album's tracks are
left for manual review. Nothing is written to any audio file here.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import patterns
from spotify_lookup import SpotifyLookup
from tags import is_various, normalize, progress, similarity, use_utf8_stdout

# An album pattern must explain this much of the album, and beat the runner-up
# by this margin, before it is trusted.
MIN_PATTERN_SCORE = 0.55
MIN_PATTERN_MARGIN = 0.15
SAMPLE_SIZE = 8
# Title similarity needed to call a Spotify hit the same work.
SAME_TITLE = 0.85
# Preference order when two patterns score within the margin. Composer-bearing
# patterns rank first: for classical compilations the composer is the wanted
# Artist value.
TIE_BREAK = [
    "composer_colon_dash",
    "composer_colon",
    "artist_paren_suffix",
    "artist_slash_prefix",
    "artist_dash_suffix",
    "artist_dash_prefix",
]

FIELDS = [
    "album", "source_root", "flac_path", "mp3_path", "track", "title",
    "current_artist", "current_album_artist", "proposed_artist", "confidence",
    "apply", "evidence", "pattern", "pattern_scores", "candidates", "notes",
]


def track_title(record: dict) -> str:
    tags = record["tags"]
    title = (tags.get("title") or "").strip()
    if title:
        return title
    return patterns.strip_track_prefix(Path(record["path"]).stem)


def album_name(record: dict) -> str:
    return record["tags"].get("album") or Path(record["path"]).parent.name


def validate_name(candidate: str, lookup: SpotifyLookup, memo: dict) -> tuple[float, str]:
    """Score 0..1 that `candidate` is a real artist, with a human-readable reason."""
    key = normalize(candidate)
    if key in memo:
        return memo[key]
    if patterns.is_known_composer(candidate):
        memo[key] = (1.0, "known composer")
        return memo[key]
    result = (0.0, "not an artist on Spotify")
    for index, variant in enumerate(patterns.name_variants(candidate)):
        hit = lookup.artist_exists(variant)
        if hit is None:
            continue
        note = f"Spotify artist '{hit['name']}'"
        if index:
            note += f" via '{variant}'"
        rating = min(1.0, hit["match"])
        if hit["followers"] < 500 and hit["popularity"] == 0:
            rating, note = min(rating, 0.6), note + " (obscure)"
        result = (rating, note)
        break
    memo[key] = result
    return result


def score_patterns(titles: list[str], lookup: SpotifyLookup, memo: dict) -> dict[str, dict]:
    """Rate every extraction strategy against one album's titles."""
    scores = {}
    for name in patterns.STRATEGIES:
        extracted = [(title, patterns.extract(name, title)) for title in titles]
        applicable = [(title, value) for title, value in extracted if value]
        coverage = len(applicable) / len(titles) if titles else 0.0
        if not applicable:
            scores[name] = {"score": 0.0, "coverage": 0.0, "validated": 0.0}
            continue
        # Sample distinct candidate names so a repeated artist costs one lookup.
        seen: dict[str, str] = {}
        for _, value in applicable:
            seen.setdefault(normalize(value), value)
            if len(seen) >= SAMPLE_SIZE:
                break
        ratings = [validate_name(value, lookup, memo)[0] for value in seen.values()]
        validated = sum(ratings) / len(ratings) if ratings else 0.0
        scores[name] = {
            "score": coverage * validated,
            "coverage": coverage,
            "validated": validated,
        }
    return scores


def choose_pattern(scores: dict[str, dict]) -> tuple[str, str]:
    """Return (winning pattern, note). Empty pattern means 'do not trust any'."""
    ranked = sorted(scores.items(), key=lambda item: -item[1]["score"])
    best, best_stats = ranked[0]
    if best_stats["score"] < MIN_PATTERN_SCORE:
        return "", f"no pattern explains this album (best {best} {best_stats['score']:.2f})"
    contenders = [
        name
        for name, stats in ranked
        if best_stats["score"] - stats["score"] < MIN_PATTERN_MARGIN
    ]
    if len(contenders) > 1:
        ordered = [name for name in TIE_BREAK if name in contenders]
        if not ordered:
            return "", f"patterns tied: {', '.join(contenders)}"
        chosen = ordered[0]
        return chosen, f"tie-break over {', '.join(n for n in contenders if n != chosen)}"
    return best, ""


def match_spotify_album(album: str, titles: list[str], lookup: SpotifyLookup) -> dict | None:
    """Find a Spotify release of the same compilation, if one exists.

    Searched under both the full album name and a disc-stripped form, because a
    3-disc rip of "50 Golden Hymns - Disc 1" is one 50-track release on Spotify.
    """
    search_names = patterns.album_search_names(album)
    # Our album names a disc, so its Spotify twin probably carries a subtitle
    # ("- Volume 2 - Great Is Thy Faithfulness") that wrecks name similarity.
    # Only then is strong track overlap allowed to stand in for a close name,
    # which keeps generic titles like "Joy To The World" from matching any of the
    # countless carol compilations that share its track list.
    multi_disc = len(search_names) > 1
    base_tokens = {
        normalize(word) for word in search_names[-1].split() if normalize(word)
    }
    best = None
    seen_ids = set()
    for search_name in search_names:
        # Deep enough to reach the later volumes of a set: "Volume 3" of
        # 50 Golden Hymns is only the seventh hit for that album name.
        for hit in lookup.search_albums(search_name, limit=10):
            if hit["id"] in seen_ids:
                continue
            seen_ids.add(hit["id"])
            spotify_tracks = lookup.album_tracks(hit["id"])
            if not spotify_tracks:
                continue
            matched = 0
            for title in titles:
                if any(similarity(title, item["title"]) >= SAME_TITLE for item in spotify_tracks):
                    matched += 1
            overlap = matched / len(titles) if titles else 0.0
            name_match = max(similarity(name, hit["name"]) for name in search_names)
            hit_tokens = {
                normalize(word) for word in hit["name"].split() if normalize(word)
            }
            subtitled = multi_disc and base_tokens and base_tokens <= hit_tokens
            # Require real track agreement plus either a believable name or, for a
            # disc of a set, a name our album name is wholly contained in.
            if overlap < 0.5:
                continue
            if name_match < 0.6 and not (subtitled and overlap >= 0.75):
                continue
            score = overlap * max(name_match, 0.75 if subtitled else 0.0)
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "overlap": overlap,
                    "name_match": name_match,
                    "name": hit["name"],
                    "tracks": spotify_tracks,
                }
    return best


def composer_consensus(title: str, hits: list[dict]) -> tuple[str, str]:
    """Identify the composer of a classical work from agreement across hits.

    Safe where a plain track search is not: a composer is a property of the work
    itself, so independent recordings all credit the same one. Genuinely ambiguous
    titles ("Piano Concerto No. 1") produce disagreement and are rejected, and a
    performer-only credit ("Royal Philharmonic Orchestra") is never accepted.
    """
    matching = [hit for hit in hits if similarity(title, hit["title"]) >= SAME_TITLE]
    if len(matching) < 2:
        return "", ""
    found: list[str] = []
    for hit in matching:
        composers = [name for name in hit["artists"] if patterns.composer_in(name)]
        if composers:
            found.append(composers[0])
    if len(found) < 2:
        return "", ""
    distinct = {normalize(name) for name in found}
    if len(distinct) != 1:
        return "", ""
    # Prefer the fullest spelling Spotify used, e.g. "Antonin Dvorak".
    chosen = max(found, key=len)
    return chosen, f"{len(found)} of {len(matching)} Spotify hits credit {chosen}"


def artist_from_album_match(title: str, album_match: dict) -> tuple[str, str]:
    best_artist, best_score = "", 0.0
    for item in album_match["tracks"]:
        score = similarity(title, item["title"])
        if score >= SAME_TITLE and score > best_score:
            named = [name for name in item["artists"] if not is_various(name)]
            if named:
                best_artist, best_score = named[0], score
    if not best_artist:
        return "", ""
    return best_artist, f"Spotify album '{album_match['name']}' track match {best_score:.2f}"


def track_search(title: str, album: str, lookup: SpotifyLookup) -> list[dict]:
    hits = lookup.search_tracks(f'track:"{title}" album:"{album}"', limit=6)
    if not hits:
        hits = lookup.search_tracks(f'track:"{title}"', limit=6)
    return hits


# A single track hit whose album name resembles ours is NOT evidence, however
# tempting it looks. Compilation names like "Joy To The World", "Rejoice" and
# "Come Let Us Adore Him" are shared by dozens of unrelated releases that also
# share their public-domain track lists, so matching per track pulled credits
# from three different Spotify albums at once (Faith Hill, The Wonder Kids,
# Santiago Brown...) and got every one of them wrong. Album identity has to be
# established across the whole album at once - that is match_spotify_album -
# or from the work itself, which is composer_consensus.


def describe_candidates(hits: list[dict], limit: int = 3) -> str:
    return " | ".join(
        f"{', '.join(hit['artists'])} ({hit['title']} / {hit['album']})"
        for hit in hits[:limit]
    )


def index_by_folder(scan: dict) -> dict[str, list[dict]]:
    """Group every known MP3 by its folder, for same-album fuzzy matching."""
    folders: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for index in ("mp3_index", "mp3_fallback"):
        for entries in scan[index].values():
            for entry in entries:
                if entry["path"] in seen:
                    continue
                seen.add(entry["path"])
                path = Path(entry["path"])
                folders[normalize(path.parent.name)].append({**entry, "stem": path.stem})
    return folders


def find_mp3(record: dict, scan: dict, folders: dict[str, list[dict]]) -> tuple[str, str]:
    flac_path = Path(record["path"])
    album = record["tags"].get("album") or flac_path.parent.name
    stem = normalize(flac_path.stem)
    primary = f"{normalize(album)}\x00{stem}"
    secondary = f"{normalize(flac_path.parent.name)}\x00{stem}"
    for key, index in ((primary, "mp3_index"), (secondary, "mp3_index"), (secondary, "mp3_fallback")):
        matches = scan[index].get(key, [])
        if len(matches) == 1:
            return matches[0]["path"], ""
        if len(matches) > 1:
            return "", f"{len(matches)} MP3s match"
    # Filenames drift between the two copies - one side had "1812 Overure"
    # corrected to "Overture" - so fall back to the closest name in the same
    # folder, but only when a single candidate stands out.
    close = [
        (similarity(flac_path.stem, entry["stem"]), entry)
        for entry in folders.get(normalize(flac_path.parent.name), [])
    ]
    strong = [entry for score, entry in close if score >= 0.9]
    if len(strong) == 1:
        return strong[0]["path"], f"matched MP3 by name similarity ({strong[0]['stem']})"
    if len(strong) > 1:
        return "", f"{len(strong)} MP3s have similar names"
    return "", "no matching MP3"


def write_xlsx(rows: list[dict], path: Path) -> str:
    """Write a filterable copy for review. Returns a status line for the summary."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        return "openpyxl not installed; skipped the .xlsx copy"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "proposals"
    sheet.append(FIELDS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([row.get(field, "") for field in FIELDS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(FIELDS))}{len(rows) + 1}"
    widths = {"album": 40, "title": 45, "proposed_artist": 28, "evidence": 45,
              "candidates": 60, "flac_path": 60, "mp3_path": 60, "pattern_scores": 40}
    for index, field in enumerate(FIELDS, 1):
        sheet.column_dimensions[get_column_letter(index)].width = widths.get(field, 16)
    try:
        workbook.save(path)
    except PermissionError:
        return f"{path.name} is open in Excel; skipped the .xlsx copy"
    return f"Review sheet: {path}"


def main() -> int:
    use_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, default=Path(__file__).with_name("01-various_artists_scan.json"))
    parser.add_argument("--report", type=Path, default=Path(__file__).with_name("02-artist_proposals.csv"))
    parser.add_argument("--cache", type=Path, default=Path(__file__).with_name("02-spotify_cache.json"))
    parser.add_argument("--offline", action="store_true", help="Use only cached Spotify responses")
    parser.add_argument("--album", action="append", default=[], help="Limit to albums containing this text")
    args = parser.parse_args()

    if not args.scan.exists():
        parser.error(f"scan not found, run 01-scan.py first: {args.scan}")
    scan = json.loads(args.scan.read_text(encoding="utf-8"))
    lookup = SpotifyLookup(args.cache, offline=args.offline)
    memo: dict[str, tuple[float, str]] = {}

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    unreadable = []
    for record in scan["sources"]:
        if "tags" not in record:
            unreadable.append(record)
            continue
        grouped[(record["root"], normalize(album_name(record)))].append(record)

    if args.album:
        wanted = [text.casefold() for text in args.album]
        grouped = {
            key: value
            for key, value in grouped.items()
            if any(text in album_name(value[0]).casefold() for text in wanted)
        }

    folders = index_by_folder(scan)
    rows: list[dict] = []
    stats = Counter()
    for number, (key, records) in enumerate(sorted(grouped.items()), 1):
        album = album_name(records[0])
        progress(number, len(grouped), "Resolving albums")
        titles = [track_title(record) for record in records]

        scores = score_patterns(titles, lookup, memo)
        pattern, pattern_note = choose_pattern(scores)
        score_text = ", ".join(
            f"{name}={stats_['score']:.2f}"
            for name, stats_ in sorted(scores.items(), key=lambda item: -item[1]["score"])
            if stats_["score"] > 0
        )
        album_match = None
        if not pattern:
            album_match = match_spotify_album(album, titles, lookup)

        for record, title in zip(records, titles):
            tags = record["tags"]
            mp3_path, mp3_note = find_mp3(record, scan, folders)
            proposed, confidence, evidence, candidates, notes = "", "review", "", "", mp3_note

            if pattern:
                extracted = patterns.extract(pattern, title)
                if extracted:
                    rating, reason = validate_name(extracted, lookup, memo)
                    proposed = extracted
                    evidence = f"{pattern}: {reason}"
                    confidence = "high" if rating >= 0.85 else "medium"
                else:
                    notes = "; ".join(filter(None, [notes, f"{pattern} found no artist in title"]))
            elif album_match:
                proposed, evidence = artist_from_album_match(title, album_match)
                if proposed:
                    confidence = "high" if album_match["overlap"] >= 0.75 else "medium"

            if not proposed:
                hits = track_search(title, album, lookup)
                found, reason = composer_consensus(title, hits)
                if found:
                    proposed, evidence, confidence = found, reason, "medium"
                else:
                    candidates = describe_candidates(hits)
                    notes = "; ".join(filter(None, [notes, pattern_note or "no corroborated artist"]))

            stats[confidence] += 1
            if not mp3_path:
                stats["missing_mp3"] += 1
            rows.append(
                {
                    "album": album,
                    "source_root": record["root"],
                    "flac_path": record["path"],
                    "mp3_path": mp3_path,
                    "track": tags.get("track", ""),
                    "title": title,
                    "current_artist": tags.get("artist", ""),
                    "current_album_artist": tags.get("album_artist", ""),
                    "proposed_artist": proposed,
                    "confidence": confidence,
                    "apply": "yes" if confidence == "high" else "",
                    "evidence": evidence,
                    "pattern": pattern or ("spotify_album" if album_match else "none"),
                    "pattern_scores": score_text,
                    "candidates": candidates,
                    "notes": notes,
                }
            )
    print()
    lookup.save()

    for record in unreadable:
        rows.append(
            {field: "" for field in FIELDS}
            | {
                "album": Path(record["path"]).parent.name,
                "source_root": record["root"],
                "flac_path": record["path"],
                "confidence": "unreadable",
                "notes": record.get("error", ""),
            }
        )

    rows.sort(key=lambda row: (row["album"], row["track"], row["title"]))
    report = args.report
    try:
        handle = report.open("w", newline="", encoding="utf-8-sig")
    except PermissionError:
        report = report.with_name(f"{report.stem}_rerun{report.suffix}")
        print(f"Report was locked; writing {report.name} instead.")
        handle = report.open("w", newline="", encoding="utf-8-sig")
    with handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Tracks examined:            {len(rows)}")
    print(f"  high confidence           {stats['high']}  (pre-ticked apply=yes)")
    print(f"  medium confidence         {stats['medium']}  (tick apply=yes to accept)")
    print(f"  needs manual review       {stats['review']}")
    print(f"Tracks with no matching MP3: {stats['missing_mp3']}")
    print(f"Spotify calls / cache hits:  {lookup.calls} / {lookup.hits}")
    print(f"Proposals: {report}")
    print(write_xlsx(rows, report.with_suffix(".xlsx")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
