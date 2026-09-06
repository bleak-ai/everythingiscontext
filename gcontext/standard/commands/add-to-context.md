---
description: Promote reviewed journal facts into context/project/ (propose, then apply)
---
Review journal files and session transcripts. Propose changes before
you write to context/project/.

1. Run `uv run context/system/scripts/journal-review.py --list`.
   Keep its JSON output. Set the review cutoff to the current ISO
   timestamp. Read every journal path in the `journal` list.
2. Skip the transcript of the current session (the hook already
   captured it). For each other path in the `transcripts` list, run
   `uv run context/system/scripts/journal-review.py --condense <path>`.
   Write each command output to a separate temporary text file under
   the scratch directory that the harness gives you. Use the OS temp
   directory when the harness gives no scratch directory. Read every
   condensed text file.
3. Collect all durable facts. Include decisions, paths, names,
   measured numbers, results, traps, and closed paths. Drop
   duplicates across sessions. Drop narration and transient chatter.
4. Read context/project/index.md and all relevant project files. For
   each fact, decide PRESENT, STALE, or MISSING. Use the Save routing
   in context/system/rules.md. PRESENT means no change. STALE replaces
   the wrong fact. MISSING adds the fact.
5. Propose one line per STALE or MISSING fact. Give its target path.
   Include each new file or folder that the file test and folder test
   require. Do not write yet.
6. Stop and wait for the exact reply `apply`. Treat any other reply
   as a rejection. Use its comments in a new proposal.
7. On `apply`, write the approved facts. Run
   `uv run context/system/scripts/sync-index-files.py --write`. Then
   run `uv run context/system/scripts/sync-index-files.py --check`.
   Fix all reported problems.
8. Count the unique session file names in the review input. Append
   this line to context/system/log.md with the review cutoff:

       - YYYY-MM-DD: journal review, N sessions, up to <iso>

9. Report one line per file changed. Never commit.
