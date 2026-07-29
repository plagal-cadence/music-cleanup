---
description: "Run a safe, repeatable music library cleanup workflow for folder structure and FLAC tags"
name: "Music Library Cleanup"
argument-hint: "Roots=M:\\MusicFlacSource; TargetFormat=Artist/Album/NN - Title.flac; Mode=dry-run|apply"
agent: "agent"
---
Use the workspace skill [music-library-cleanup](../skills/music-library-cleanup/SKILL.md) to execute this task.

User request:
{{input}}

Execution requirements:
1. Confirm cleanup scope and paths from input.
2. Default to dry-run unless the input explicitly says apply.
3. Run inventory and audit steps first, then propose apply actions.
4. Before any rename/move/tag-write step, summarize intended changes.
5. Produce a final report with counts:
   - files scanned
   - folders renamed
   - tags updated
   - unresolved items
6. Include paths to generated CSV/TXT reports.

If input is missing required details, ask only the minimum questions needed to proceed.
