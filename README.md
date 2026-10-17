# music-cleanup

Scripts and reports for organizing music collections, reconciling FLAC and MP3 libraries, and preparing DAC comparison material.

## FLAC-to-MP3 Mapping Workflow

This workflow compares the FLAC albums listed by `01-inventory.py` with MP3 libraries. It is report-first and does not modify music files during mapping.

### Run Everything

Run the complete workflow with one command. It inventories FLAC albums, maps tracks, writes all missing-track reports, and creates the review playlist:

```powershell
python d:/Code/music-cleanup/cleanup-cds/00-run-music-cleanup.py
```

The default MP3 roots are the five configured `M:` roots below. To use another set, repeat `--mp3-root`:

```powershell
python d:/Code/music-cleanup/cleanup-cds/00-run-music-cleanup.py `
	--mp3-root "M:\Music\Christian\MusicFromCDsFromFlac" `
	--mp3-root "M:\Music\Classical\MusicFromCDsFromFlac"
```

### File Roles In `cleanup-cds`

The orchestrator actively runs these scripts in numbered order: `01-inventory.py`, `02-mapping.py`, `03-missing-track-report.py`, `04-album-summary.py`, `05-playlist.py`, and `06-track-analysis.py`. `00-run-music-cleanup.py` coordinates them, and `requirements.txt` supplies the `mutagen` dependency.

The CSV and M3U files are generated outputs that later steps consume where applicable. In particular, `02-mapping.csv` feeds the missing-track reports, `03-missing-track-report.csv` feeds the playlist and track analysis, and the album-summary report is a review output.

The `.xlsx` files are manual Excel conversions of CSV reports. They are not read by the automated process and can be regenerated manually whenever needed.

### 1. Run the mapper

Provide every MP3 root explicitly. On Windows PowerShell, use one `--mp3-root` option per root:

```powershell
python d:/Code/music-cleanup/cleanup-cds/02-mapping.py `
	--mp3-root "M:\Music\Christian\MusicFromCDsFromFlac" `
	--mp3-root "M:\Music\Classical\MusicFromCDsFromFlac" `
	--mp3-root "M:\Music\Secular\MusicFromCDsFromFlac" `
	--mp3-root "M:\MusicFromCDsRussMp3\_Classical" `
	--mp3-root "M:\MusicFromCDsRussMp3\_Secular" `
	--top 5
```

Output: `02-mapping.csv`

The mapper first checks for an exact filename stem in candidate album folders. Rows marked `mp3_found=no` mean that exact lookup failed; they do not necessarily mean that an MP3 is physically absent. The candidate column is a fuzzy-search result across the indexed MP3 roots and must be reviewed, especially at lower scores.

### 2. Build missing-track reports

```powershell
python d:/Code/music-cleanup/cleanup-cds/03-missing-track-report.py
python d:/Code/music-cleanup/cleanup-cds/04-album-summary.py
```

Outputs:

- `03-missing-track-report.csv`: every unresolved FLAC row and all fuzzy candidates.
- `04-album-summary.csv`: album-level counts with candidate samples.

### 3. Create a playlist for review

```powershell
python d:/Code/music-cleanup/cleanup-cds/05-playlist.py
```

Output: `05-playlist.m3u`, containing the full FLAC paths from `03-missing-track-report.csv` in CSV order.

### 4. Analyze tracks and path nodes

```powershell
python d:/Code/music-cleanup/cleanup-cds/06-track-analysis.py
```

Output: `06-track-analysis.csv`, with only the top fuzzy MP3 candidate for each missing FLAC track. It includes the FLAC root, expected MP3 root, candidate MP3 root, root-mapping status, directory paths, filename prefixes, and an `issue` column identifying filename or path/name differences. Exact matches are excluded; file suffixes, `flac_album`, and separated path-node columns are omitted.

## Verified Results

The latest orchestrator dry run inspected 5,805 FLAC tracks across 489 FLAC album directories. It reported 110 exact-match misses across 34 albums. No music files were modified.

The unresolved rows are exact-match misses, not necessarily absent files. An earlier report showed 87 normalized FLAC/destination filename-prefix matches and 12 mismatches. Among those 87 matches, all 87 retained the same artist folder; 63 retained the same album folder name, while the rest used naming variations such as year prefixes or punctuation/spelling changes. Counts can change when the live M: library changes.

## Lessons Learned

- A fuzzy candidate that exists is not proof that it is the same recording. Keep the score and inspect artist, album, track number, and candidate path together.
- Exact filename matching is intentionally strict. Trailing spaces, punctuation, accents, and small spelling differences can produce `mp3_found=no` even when the corresponding MP3 exists.
- Album-folder names vary independently of track identity. Compare artist and album components separately; do not treat an absolute-path mismatch as a missing file.
- Candidate strings can contain semicolons inside filenames. Split candidate records only at semicolons followed by a numeric score, not at every semicolon.
- On PowerShell, Bash heredocs such as `python - <<'PY'` do not work. Put multi-line Python in a `.py` file and execute it with the selected interpreter.
- Keep source files, reports, and logs separate. The mapping and copy scripts never delete, rename, or overwrite music files during dry runs.
- A CSV opened by Excel or another viewer can be locked. If regeneration fails with `PermissionError`, close the report or write to a temporary output path while investigating.
- Use the repository virtual environment when available: `d:/Code/music-cleanup/.venv/Scripts/python.exe`.
- Install the Python dependency before running the inventory step: `d:/Code/music-cleanup/.venv/Scripts/python.exe -m pip install -r d:/Code/music-cleanup/cleanup-cds/requirements.txt`.
