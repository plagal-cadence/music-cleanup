---
name: music-library-cleanup
description: 'Use when the user wants to clean up a music library: normalize artist/album folder names, reconcile FLAC folder mappings, detect non-FLAC files, audit missing or inconsistent tags, standardize track naming, flatten or reorganize album folders, and prepare copy-ready ordered track sets. Best for workflows involving CSV inventory scripts, safe dry-runs, and bulk rename/tag fixes with logs.'
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
     - `list_albums.py`
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
