---
description: Save this session's durable facts into context/ (apply, then report)
---
Follow the save procedure in context/system/rules.md. Apply it
directly. Never ask for approval.

1. Read context/project/index.md and the files on the
   relevant paths.
2. Collect this session's durable facts: real URLs, field names,
   measured numbers, traps hit, closed paths, decisions. No narration.
   Cover the whole session, not only the recent part.
3. For each fact decide: PRESENT (already in a file, skip), STALE
   (contradicts a file, replace), or MISSING (write). Route each to
   ONE existing project/ file. For a new file apply the depth-first
   placement law and the four one-folder-one-goal questions.
4. Write in ASD-STE100 Simplified Technical English, in the target
   the target file's format (dated evidence "(seen YYYY-MM-DD: ...)";
   history: one dated append line; task: a backlog task file).
5. Refresh the map's Status and mirror it into README.md when it
   changed. Apply tier 3 changes and append their log.md
   entry.
6. Run `uv run context/system/scripts/sync-index-files.py --write`, then `--check`.
7. End with the save report: one line per file changed, each new
   file with its depth-first path and the shallowest rejected
   folder, and every tier 3 item. Never commit.
