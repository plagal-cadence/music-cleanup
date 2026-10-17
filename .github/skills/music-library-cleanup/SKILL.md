---
name: music-library-cleanup
description: 'Use when the user wants to clean up a music library: normalize artist/album folder names, reconcile FLAC folder mappings to MP3 folders, detect non-FLAC files, audit missing or inconsistent tags, standardize track naming, flatten or reorganize album folders, and prepare copy-ready ordered track sets. Best for workflows involving CSV inventory scripts, safe dry-runs, and bulk rename/tag fixes with logs.'
---

# Music Library Cleanup Skill

## Purpose
Use this skill for end-to-end cleanup of music folders and tags with safety checks, dry-runs, and reproducible logs.

## Use When
- User asks to clean music file structure.
- User asks to fix FLAC tags or naming consistency.
- User asks to reconcile album folders and FLAC source folders.
- User asks to build ordered copy sets for listening tests.

## Do Not Use When
- The task is unrelated to music files.
- The user asks only for a one-line command with no cleanup workflow.

## Inputs To Confirm
- Library root path(s), for example M:\Music and M:\MusicFlacSource.
- Target format rules, for example `Artist/Album/NN - Title.flac`.
- Tag policy, for example required tags: Artist, Album, Title, Tracknumber, Date, Genre.
- Whether to allow destructive changes (rename/move/tag-write) or dry-run only.

## Safety Rules
1. Always run discovery and reporting before edits.
2. Prefer dry-run first; require explicit confirmation before apply steps.
3. Keep change logs in CSV or TXT under the workspace root.
4. Never delete files unless explicitly requested.

## Workflow
1. Inventory:
   - Build or refresh album inventory CSV files.
   - Use existing scripts when present:
   - `01-inventory.py`
     - `list_albums_rated.py`
2. Structure Audit:
   - Detect folder naming mismatches and FLAC source mapping issues.
   - Use existing scripts when present:
     - `list_albums_suggest_flac_folder_renames.py`
     - `list_albums_adjust_flac_folder_names.py` (dry-run first, then `--apply` only with confirmation)
3. File-Type Audit:
   - Detect files that are not FLAC where FLAC-only is expected.
   - Use existing script when present:
     - `find_non_flac_files.py`
4. Tag Audit:
   - Report missing/invalid tags and track-number format issues.
   - Produce a CSV report with file path and missing fields.
5. Normalization:
   - Rename files/folders to the agreed naming rule.
   - Resolve collisions safely by suffixing rather than overwriting.
6. Verification:
   - Re-run audits and compare before/after counts.
   - Summarize exactly what changed and what remains unresolved.

## FLAC-to-MP3 Reconciliation

For the established FLAC-to-MP3 workflow in `d:/Code/music-cleanup/cleanup-cds`:

The complete workflow can be run with `00-run-music-cleanup.py`. It runs the FLAC inventory, mapper, complete missing-track report, album summary, review playlist, and track-level path-node analysis in sequence. It does not copy staged MP3 files.

The inventory step requires `mutagen`; install the workspace dependencies from `requirements.txt` before running the orchestrator.

1. Extract FLAC roots from `01-inventory.py` and run `02-mapping.py` with each MP3 root supplied through its own `--mp3-root` option.
2. Treat `mp3_found=no` as an exact-match miss, not proof that the MP3 is absent. Inspect `mp3_path_or_candidates`; fuzzy candidates are ranked suggestions and may be unrelated.
3. Use `03-missing-track-report.py` for a complete per-track report, `04-album-summary.py` for counts, and `05-playlist.py` for a review playlist.
4. Use `06-track-analysis.py` for one row per candidate track with separate numbered nodes for each FLAC and candidate MP3 path.

### Reconciliation Lessons

- Compare artist folder, album folder, and filename independently. FLAC and MP3 roots are expected to differ.
- Normalize punctuation, accents, and whitespace for comparison, but preserve original paths in reports.
- Candidate parsing must allow semicolons inside filenames; only a semicolon followed by a numeric score starts the next candidate.
- A dry run is the required discriminating check before any copy, rename, or tag operation.
- PowerShell does not support Bash heredocs. Use standalone Python files for multi-line analysis.
- Close CSV files in Excel before regeneration; Windows file locks can cause `PermissionError`.

## Output Requirements
- A concise summary with:
  - files scanned
  - folders renamed
  - tags updated
  - unresolved items
- Paths to generated reports.
- If apply mode was used, include rollback guidance where feasible.

## Communication Style
- Keep updates short and action-oriented.
- For each apply step, state what will change before running it.
- After each major step, report counts and next action.
