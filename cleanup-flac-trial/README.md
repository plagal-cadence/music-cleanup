# FLAC Trial Cleanup

`analyze_and_move_complete_albums.py` scans `M:\MusicTrial\FlacTrial` and writes a CSV report. By default it does not move anything.

An eligible album must contain only FLAC files, have readable FLAC metadata, use contiguous track numbers when track numbers are present, and resolve to `Christian`, `Secular`, or `Classical`. Category detection uses the path, genre, and artist tags. Source detection uses path names for common services such as Spotify, Qobuz, Tidal, Apple Music, Amazon Music, YouTube Music, and Deezer; unmatched paths use `UnclassifiedSource`.

Planned destinations use this layout:

```text
M:\MusicFlacSource\<Category>\<Source>\<Artist>\<Album>
```

Run a report-only scan:

```powershell
& d:\Code\music-cleanup\.venv\Scripts\python.exe .\analyze_and_move_complete_albums.py
```

Add custom source matching rules with `--source-rule "text in path=FolderName"`. Review the CSV report, then repeat with `--apply` to move eligible albums. Existing destination folders are reported as collisions and are never overwritten.

To move every album whose report value is `tracks_sequential=yes` while preserving its path below the trial root:

```powershell
& d:\Code\music-cleanup\.venv\Scripts\python.exe .\analyze_and_move_complete_albums.py --move-sequential-to M:\MusicTrialFlacFull --apply
```

## Full albums only (E: drive)

`analyze_and_move_full_albums.py` scans `E:\MusicTrial\FlacTrial` and writes `analyze_and_move_full_albums.csv`. It only looks for full albums. Category and source are ignored.

An album is a folder with FLAC files directly inside it. Disc subfolders such as `CD1` or `Disc 2` are merged into their parent folder. An album counts as `full` when:

- every FLAC file is readable and has a track number
- the tracks on each disc run from 1 to N with no gaps or duplicates, and N matches any `tracktotal`/`totaltracks` tag
- no discs are missing, checked against any `disctotal`/`totaldiscs` tag
- the folder has no other audio formats (mp3, ape, wav, ...). Artwork, cue, log, and txt files are allowed and move with the album.
- the files in each disc folder share one album tag, ignoring "Disc N" suffixes (box sets may use a different title per disc)
- a whole-disc FLAC image named in a `.cue` file is skipped for track counting when split tracks are also present. It still moves with the album.
- the folder has no nested album folders

The `missing` column shows which tracks or discs are missing from incomplete albums.

```powershell
& d:\Code\music-cleanup\.venv\Scripts\python.exe .\analyze_and_move_full_albums.py
& d:\Code\music-cleanup\.venv\Scripts\python.exe .\analyze_and_move_full_albums.py --apply
```

The `--apply` command moves full albums to `E:\MusicTrialFlacFull` and keeps each album's path relative to the trial root. Existing destinations are reported as collisions and never overwritten. Use `--trial-root`, `--destination-root`, or `--report` to change the defaults.
