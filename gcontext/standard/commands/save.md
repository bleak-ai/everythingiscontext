---
description: Save this session's durable facts into context/ (apply, then report)
---
Follow the Save section of context/system/rules.md. Apply it
directly. Never ask for approval.

1. Read context/project/index.md and the files on the relevant
   paths.
2. Collect this session's durable facts: decisions, real paths and
   names, measured numbers, results, traps hit, closed paths. No
   narration. Cover the whole session, not only the recent part.
3. For each fact decide: PRESENT (already in a file, skip), STALE
   (contradicts a file, replace the line), or MISSING (write). Route
   each fact to one file: go down while a folder names something the
   fact shares, then the file of its subject. Apply the file test
   and the folder test from rules.md before you create a file or a
   folder.
4. Write short sentences in the target file's format. A history fact
   is one dated line in log.md.
5. Run `uv run context/system/scripts/sync-index-files.py --write`,
   then `--check`. Fix what it reports.
6. End with the save report: one line per file changed. Never
   commit.
