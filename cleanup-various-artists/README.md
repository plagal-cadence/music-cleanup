# Various Artists cleanup

Finds tracks tagged `Various` / `Various Artists` in **both** Artist and Album Artist
across the FLAC sources in [roots.py](roots.py), works out the real artist of each
track, and writes it to the FLAC and its converted MP3. Album Artist is left alone:
on a compilation `Various` is correct there.

Artist **and Title** are written from the proposals sheet verbatim, so editing the
`title` column is how you correct a title — usually to drop the artist credit that
padded it, since that now lives in Artist. Leave `title` as it came out of
`02-resolve.py` and the tag on disk is left unchanged.

## Why Spotify is used the way it is

MusicBrainz resolved 3 of 149 tracks. Spotify has the opposite failure: it always
answers, and on these compilations the answer is often confidently wrong. Searching
the bare titles from your discs returns Victony's Afrobeats hit for `Soweto` on a
smooth-jazz compilation, Foo Fighters for `The Feast`, Forrest Frank for
`Amazing Grace`.

So Spotify is never asked "who plays this track". It is asked narrower questions it
answers reliably:

1. **Is this string an artist?** Your filenames usually already contain the artist,
   but the direction flips between albums — `Chris Rice - Love Like Crazy` puts it
   first, `Love Kills - Freddie Mercury` puts it last, `Moonlight Sonata-Beethoven`
   uses a bare dash. Spotify decides which side is a real artist, per album.
2. **Is this compilation on Spotify?** If a release genuinely matches on name *and*
   track list, its per-track credits are used. This is what resolves the
   `50 Golden Hymns` discs against Spotify's `Volume 1/2/3`.
3. **Who composed this work?** For classical titles, agreement across independent
   recordings identifies the composer, because the composer is a property of the
   work rather than the pressing.

Anything that survives none of those checks keeps its `Various` tag and is listed
for manual review with Spotify's candidates alongside. Per the project decision,
Artist is set to the **composer** for classical tracks, and no uncorroborated guess
is ever written.

### A trap worth keeping in mind

Matching a *single* track to a Spotify album whose name resembles yours looks like
corroboration and is not. `Joy To The World`, `Rejoice` and `Come Let Us Adore Him`
are shared by dozens of unrelated releases that also share their public-domain track
lists, so this pulled credits from three different albums at once and got Faith Hill,
The Wonder Kids and Santiago Brown — all wrong. Album identity is only ever
established across a whole album at once.

## Running it

```powershell
cd d:\Code\music-cleanup\cleanup-various-artists
$py = "d:\Code\music-cleanup\.venv\Scripts\python.exe"

& $py .\01-scan.py       # read tags from the roots  -> 01-various_artists_scan.json
& $py .\02-resolve.py     # propose artists           -> 02-artist_proposals.csv/.xlsx
& $py .\03-apply.py       # dry run: report only
& $py .\03-apply.py --apply

& $py .\04-rename.py      # dry run: album folder names, filenames, Album tags
& $py .\04-rename.py --apply

& $py .\05-regroup.py     # dry run: which album folder belongs under which artist
& $py .\05-regroup.py --apply
```

Requires `mutagen` and `spotipy` (`openpyxl` only for the `.xlsx` review copy).

### Reviewing proposals

Open `02-artist_proposals.xlsx` and filter on `confidence`:

| confidence | meaning | `apply` column |
| --- | --- | --- |
| `high` | corroborated, or a composer surname from the title itself | pre-filled `yes` |
| `medium` | name-shaped and pattern-derived, but Spotify could not confirm it | blank, your call |
| `review` | nothing trustworthy found; `candidates` lists Spotify's guesses | blank |

`03-apply.py` writes a row only when `apply` says `yes` (`y`, `true`, `1` also count).
Edit `proposed_artist` and `title` freely — both are written verbatim.

A row is skipped as `mismatch` when its `title` looks unrelated to the one on disk,
which is how a sheet that has slipped out of step with the files gets caught before
it writes Haydn over Franck. Rewriting a title by hand trips the same check, so put
**`retitled`** in that row's `apply` cell to mean "approved, and the title really is
meant to be this different". That grants the row the two things a rewritten title
needs, and only for that row: the guard is waived, and the Title is written even
where the Artist is already correct and so nothing else about the row would change.
Every other row keeps its protection, and the number of waived rows is printed when
the run starts.
`--include-medium` accepts every medium row you left blank. The `evidence` and
`pattern_scores` columns show exactly why each artist was chosen.

### Saving from Excel 2013

Excel 2013 has no "CSV UTF-8" (that arrived in 2016), so **save as `Unicode Text
(*.txt)`**. It is the only lossless option in that version: UTF-16, tab separated.
`03-apply.py` reads it, and with no `--proposals` flag it uses whichever of
`02-artist_proposals.csv` / `.txt` was saved last, printing the name it picked.

The three CSV flavours all narrow the sheet to one 8-bit code page, and characters
outside it become `?` **when Excel saves**, before anything here can read the file:

| Save as | Encoding | Cost |
| --- | --- | --- |
| `Unicode Text (*.txt)` | UTF-16 | none |
| `CSV (Comma delimited)` | Windows-1252 | loses `ř č ō ł`; keeps `’ – —` |
| `CSV (MS-DOS)` | OEM/cp850 | also loses `’ – — “ ”` — turned `Man’s` into `Man?s` |
| `Text (Tab delimited)` | Windows-1252 | same as plain CSV |

`03-apply.py` sniffs encoding and delimiter for all of them, choosing between
Windows-1252 and OEM by which decoding yields accented letters rather than stray
punctuation. That recovers a mis-saved file but cannot recover a `?`.

### Useful flags

- `02-resolve.py --album "Jukebox"` — resolve only matching albums.
- `02-resolve.py --offline` — reuse `02-spotify_cache.json`, no network. Every
  response is cached, so re-runs are free and reruns after tuning are fast.
- `03-apply.py --force` — overwrite even where Artist is no longer `Various`.
- `03-apply.py --retitle` — fix Title on **every** track an earlier run already gave
  the right Artist. Without it those are skipped, so each run only touches its own
  batch; `apply=retitled` does the same for one row, which is usually what you want.
- `03-apply.py --ignore-title-mismatch` — waives the title guard for **every** row in
  the run. Rarely what you want: the guard is the only thing standing between a
  misaligned sheet and the wrong track, and one blunt flag cannot tell your
  deliberate retitles from a row that slipped out of step. Prefer `apply=retitled`
  below.
- `03-apply.py --log 03-apply_log_batch2.csv` — **use this on every run after the
  first.** The log is opened for writing, so a second default run would overwrite the
  undo record of the first, and those rows now read as `already_set` so their original
  `Various` could not be recovered from the new log.
- `03-apply.py --rollback 03-apply_log.csv --apply` — restore the previous values.
  Only the fields that run actually changed are put back.

## Album names: `04-rename.py`

`03-apply.py` only ever touches Artist and Title. Album lives one level up — it is a
property of the folder, not the track — so the albums whose *name* was wrong are
corrected by `04-rename.py` instead, from the `ALBUM_FIXES` table at the top of it.
Each entry names the folder as it is now, the folder it should be, and the Album tag
every track in it should carry. Per album, in every root in [roots.py](roots.py):

1. runs of spaces inside filenames are collapsed to one
2. the Album tag is set, where it differs
3. the folder is renamed

That order is deliberate. The folder rename goes last so the paths written to the log
stay valid while the run is still going, and so a rollback — which replays the log
backwards, restoring the folder name first — finds the files where the log says they
are. Dry run by default, `--apply` to write, `--rollback 04-rename_log.csv --apply` to
undo. As with `03-apply.py`, pass `--log` a fresh name on later runs or the first
run's undo record is overwritten.

Re-running is safe and is how a partial run is finished: a folder is matched under
either its old or its corrected name, and only what still differs is changed. Two
things it will not do — rename onto a name already taken, or rename a folder while
another program holds a file inside it. The second is the common one: Windows fails
the directory rename if a player still has a track open, or if an Explorer window is
sitting on that very folder. The run reports the folder and carries on, so closing the
program and re-running picks up just the leftovers.

Album folder renames invalidate every path in `01-various_artists_scan.json` and
`02-artist_proposals.csv`. Re-run `01-scan.py` before the next `02-resolve.py`.

## Folder placement: `05-regroup.py`

The move that brought `M:\MusicFromCDsRussFlac` into `M:\MusicFlacSource` grouped
albums by the **Artist** tag rather than **Album Artist**, so every compilation was
shredded into one folder per performing artist. `Time-Life Library of Classical
Favorites Disc B` became sixteen folders holding one track each, under `Albeniz`,
`Chopin`, `Clarke` and thirteen more. The same run also sent the whole `_Classical`
subtree into the Secular root instead of the Classical one.

`05-regroup.py` puts both right. What it does **not** do is group on Album Artist
either, because that tag is not trustworthy here: fourteen Mozart box sets carry
`Album Artist = Various`, and obeying it would file `Piano Sonatas` as a
compilation. Instead the intended layout is read from `M:\MusicFromCDsRussMp3`,
which the move never touched and which is therefore still an intact copy of how
the discs were organised — album folder name maps to the subtree and artist folder
it belongs under. Only `Various Artists` is renamed on the way in, to `Various`,
which is what the destination roots already use. The fourteen Mozart sets are
printed under "Album Artist worth reviewing" and left where the source tree had
them, so the tag can be fixed later without the folders having moved first.

Because that same tree is also the MP3 side that was never moved at all, the run
does three things at once: regroups the FLAC roots, regroups the MP3 roots, and
moves the Russ MP3 tree into `M:\Music`. `--skip-import` leaves that last part out.

A fourth pass owes nothing to the Russ trees and runs over **every** root in
[roots.py](roots.py), Christian included: a root holding both `Various` and
`Various Artists` splits one artist across two folders for no reason, so the second
is folded into the first. Only names that *are* the word are folded, which is why
`Big Band - Various` stays where it is — that is a band name that happens to end in
it, not a compilation folder.

Two safeguards matter:

- An album folder is only accepted as the counterpart of a Russ album when at least
  70% of its tracks are recognisable there. Filenames differ between the trees by
  more than punctuation — the MP3s are `01 - Title.mp3` and the FLACs `01 Title.flac`,
  accents survive in one tree but not always the other, and the FLAC name often
  spells out what the MP3 name abbreviated — so tracks are matched on normalized
  stems, fuzzily, and by containment. Anything below the threshold is reported and
  skipped rather than moved on a guess.
- Nothing is ever overwritten. A merge target usually already exists, since the
  first fragment of a shredded compilation creates the folder and the rest merge
  into it, and a track already there under a name differing only in spacing is
  still the same track. Those are reported as conflicts and left alone, which is
  how the one album that had already reached `M:\Music` survived the import intact.

Dry run by default, `--apply` to write, `--rollback 05-regroup_log.csv --apply` to
undo. As with the scripts above, pass `--log` a fresh name on later runs. Re-running
is safe: an album already at its target is not a move, so a second run is a no-op.

As with `04-rename.py`, this invalidates every path in
`01-various_artists_scan.json`, so re-run `01-scan.py` before the next
`02-resolve.py`.

## Reapplying

Applying is safe to repeat: a track whose Artist and Title already hold the proposed
values is skipped, and so is one whose Artist is no longer `Various` or whose title on
disk belongs to a different track altogether.

"Already holds the value" is judged on letters and digits alone, so correcting only
the punctuation or capitalisation of a title is not something this writes. Runs of
spaces are the exception, since they are never deliberate and comparing without
whitespace would make them permanent: `Pomp and Circumstance   March No. 1` is
rewritten to the single-spaced title in the sheet.
