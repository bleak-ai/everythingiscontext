# /check-structure

Check context/project/ against the shape rules and propose the
smallest tree that passes them. Propose first, apply only on "apply".

## Steps

1. Read context/system/rules.md, section "Shape: few files, each one
   rich". Then read every .md under context/project/, index files
   included.
2. Run `uv run context/system/scripts/sync-index-files.py --check`.
   Report failures as-is; do not fix them here.
3. File test. For every fact line, name the thing it is about. A
   thing with three or more facts gets its own file. A file with
   fewer than three facts folds back into its parent subject, unless
   it is the only file about a thing the project tracks on its own.
   Two files about one thing are merged.
4. Pair test. At every level, for every two entries, name the
   smallest expression that covers both. When it is smaller than the
   folder's own name and no folder has it, that is a missing folder;
   every sibling it covers moves in. A folder never holds one file.
   A folder never names the whole project. Repeat inside every new
   folder.
5. Write the proposal in the reply: the target tree, then one line
   per move (split file, merge files, new folder, move, rename) with
   a one-line reason. When the tree already passes, say "structure
   passes" and go to step 7.
6. Stop. Wait for "apply". Any other answer is a rejection: take the
   comment into account and propose again from step 3.
7. On apply: move the fact and pointer lines, create each new folder
   with an index.md whose purpose says what its entries share, give
   each new file a title and a purpose line, rewrite every pointer
   that named a moved file, and delete a source that has no fact
   lines left.
8. Run `uv run context/system/scripts/sync-index-files.py --write`,
   then `--check`. Fix what it reports.
9. Count fact lines (lines that start with `- ` in every .md under
   context/project/ except index.md) and folders under
   context/project/. Append to context/system/log.md:

       - YYYY-MM-DD: structure check, N facts, M folders. <one line on what moved>

   Append the line also when the structure passed, so the tracker
   restarts at zero.
10. Report: the moves applied, the log line, and the check result.
