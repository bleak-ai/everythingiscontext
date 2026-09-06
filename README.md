# gcontext

gcontext is a folder standard. It gives an AI agent a memory of your
project.

## The problem

An AI agent forgets everything between sessions. You repeat the same
facts. The agent makes the same mistakes. The usual fix is one large
notes file. That file grows. Nobody reads it. The agent stops finding
facts in it.

## The idea

gcontext replaces that file with a folder named `context/`. The agent
writes each durable fact into `context/`. Each fact goes into the file
of its subject. Files that share a name go into a folder with that
name. The tree grows from the content. You do not design it in
advance.

One rule decides where a fact goes: a path is a chain of common
denominators. A folder name is what all its entries share. A file
holds all the facts about one subject.

From that rule follow three tests:

- A thing gets its own file when three facts are about it.
- Two files that share a name get a folder with that name.
- At every level, two entries always share something. When what they
  share is smaller than the folder they sit in, a folder is missing.

Read `docs/principles.md` for the idea on one page. Read
`docs/standard.md` for the complete standard. That file is the whole
standard. There is no other rule file.

## What you get

After you install gcontext in a project, three things happen.

1. Save. The agent writes durable facts into `context/project/`
   while you work. A hook forces a save every five turns. You do not
   ask for it. You review the git diff.
2. Track. Your status line shows one line after every turn. It tells
   you how many facts and folders the agent added since the last
   structure check. The line is green, amber, or red.
3. Check. When the line is red, you run `/check-structure`. The agent
   proposes the smallest tree that passes the rules. You say
   "apply". The agent moves the content. The counter goes back to
   zero.

A git hook stops each commit that breaks the structure.

## How to start

You need `uv` (https://docs.astral.sh/uv) and Claude Code.

1. Install the CLI.

   ```bash
   uv tool install gcontext-ai
   ```

2. Go to the root of your project. Run init.

   ```bash
   gcontext init
   ```

   init writes these files. It does not overwrite a file that exists.

   - `context/index.md` and `context/project/index.md`: the entry
     points of the memory.
   - `context/system/rules.md`: the standard.
   - `context/system/log.md`: the history of structure checks.
   - `context/system/scripts/`: the scripts listed below.
   - `.claude/commands/save.md` and `check-structure.md`: the two
     Claude Code commands `/save` and `/check-structure`.
   - `.claude/settings.json`: the Stop hook that forces a save.
   - `CLAUDE.md`: two lines that tell the agent to read the memory
     and to follow the rules.

   init also sets `git config core.hooksPath` to the bundled hooks
   folder. Then it runs the structure check.

3. Add the tracker to your Claude Code status line. init prints the
   command. It is:

   ```bash
   uv run --no-project python3 context/system/scripts/track-context-changes.py . --color
   ```

4. Work as usual. Ask the agent questions. Let it do tasks. The agent
   saves facts on its own. Type `/save` when you want a save now.

5. When the status line is red, type `/check-structure`. Read the
   proposal. Type "apply".

## What each script does

init writes all scripts to `context/system/scripts/`. Run each one
with `uv run`.

### sync-index-files.py

This script keeps every `index.md` correct. Each folder has one
`index.md`. The index has a hand-written purpose line at the top and
a generated list of entries below a marker. The script copies the
purpose line of each entry into the parent index.

- `--write` regenerates every index list.
- `--check` reports problems and exits with code 1. It reports: a
  folder without `index.md`, a name with an uppercase letter, a file
  without a purpose line, an index entry that names a missing entry,
  an existing entry that the index omits, a `TODO(describe)`
  placeholder, and a pointer line whose target does not exist.

The agent runs `--write` after every save. The pre-commit hook runs
`--check`.

### track-context-changes.py

This script prints one line for the status line. It counts the fact
lines and the folders under `context/project/`. It compares the
count with the last structure check line in `context/system/log.md`.

Output example:

```text
context: +4 facts, +0 folders since the structure check (2026-09-06), structure ok
```

The `--color` flag adds a color. Green means fewer than 10 new facts
and fewer than 3 new folders. Amber means fewer than 20 facts and
fewer than 5 folders. Red means more. The line tells you what to do
next. The script always exits with code 0.

### save-every-n-turns.py

This script is a Claude Code Stop hook. Claude Code runs it after
every assistant turn. The script counts the turns of the session.
On every fifth turn it tells the agent to save now. The agent reads
the Save section of the rules, writes the facts it learned, runs
`sync-index-files.py --write`, and reports the paths. Then it
continues its task.

The script never triggers itself. It exits without output when a
save turn is already in progress. Set the environment variable
`GCONTEXT_SAVE_EVERY` to change the interval.

### githooks/pre-commit

This shell script is the git pre-commit hook. It does two checks.

1. It looks for structure changes in the staged files: a deleted
   markdown file, a renamed markdown file, or a new markdown file
   below the second level of `context/project/`. If it finds one
   and `context/system/log.md` is not in the commit, the commit
   stops. A structure change needs one line in the log.
2. It runs `sync-index-files.py --check`. If the check fails, the
   commit stops.

init enables the hook with `git config core.hooksPath`. To bypass it
once, commit with `--no-verify` and tell the owner why.

### rules_config.py

This module reads optional rule toggles for `sync-index-files.py`.
The standard does not use toggles at the moment. The module returns
no toggles when no toggle file exists.

## The two commands

- `/save`: the agent collects the durable facts of the session and
  writes each one into the file of its subject. It does not ask for
  approval. It reports one line per file it changed.
- `/check-structure`: the agent reads every file under
  `context/project/`, applies the file test, the folder test, and
  the pair test, and proposes the target tree. It waits for
  "apply". Then it moves the content, regenerates the indexes, and
  appends a structure check line to `log.md`.

## The CLI

- `gcontext init [dir]`: write `context/` from the bundled standard.
- `gcontext check [dir]`: run the structure checks.
- `gcontext serve [dir]`: start the MCP server that exposes
  `context/` to other runtimes. See `docs/mcp.md`.
- `gcontext install <package-folder> [dir]`: install a package into
  `context/packages/`.

See `docs/cli.md` for arguments and exit codes.

## What it is not

- Not a database. Not a vector store. Plain markdown in git.
- Not a config file the agent reads once. The agent writes there too.
- Not tied to one tool. The rules are one file. Any agent that can
  read and write files can follow them. The hook and the commands
  are for Claude Code.

## Documentation

- `docs/principles.md`: what gcontext is and why, on one page.
- `docs/standard.md`: the standard, version 1.0.
- `docs/cli.md`: commands, arguments, exit codes.
- `docs/mcp.md`: the MCP server.
- `CHANGELOG.md`: releases.

## License

MIT
