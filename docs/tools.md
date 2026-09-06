# The seven tools

Every connected client gets the same seven tools, and nothing else: if a capability is not on this list, the agent does not have it. All paths are relative to the state folder, and no path escapes it. This page describes each tool for a human reading the transcript; the agent receives its own instructions for them.

## read_file

Returns the content of one file. This is the on-demand counterpart to attaching a resource: the agent calls it mid-task when it decides a file matters. The one exception is `secrets.env`, which the tool refuses to read, so secret values never enter the context window.

## write_file

Writes one file, creating parent directories as needed. Updating an existing file returns a unified diff of the change (capped at 200 lines), so every write the agent makes is auditable in the transcript; creating a file returns its size and line count. It refuses to write `secrets.env`. A write can carry a warning when it leaves a folder's index.md out of sync with its files; the write still happens, and the agent is expected to fix the index.

## list_dir

Lists one directory: subdirectories first (with a trailing slash), then files with sizes. Machine folders (`.venv`, `.git`, `__pycache__`, `node_modules`) are hidden.

## grep

Searches project files with a regular expression and returns `path:line: matching-line` hits, capped at 100 matches. An optional filename glob narrows the search. It skips the same machine folders as list_dir, plus `secrets.env`. This is how the agent finds a playbook or a log before reading it.

## run_script

Runs a saved Python script from the project by path, in the project's own virtual environment, with the declared connection dependencies installed and secret values injected as environment variables. Output is scrubbed of secret values before it returns. The result is plain text starting with a status line in the form `[exit N | M ms]`, extended with `timed out` or `truncated` when those apply, then stdout, then a `[stderr]` block when present, and a `[hint]` line when the failure was a missing package.

## run_adhoc_script

The same execution environment as run_script, but for one-off code the agent writes inline instead of a saved file. The intended flow: explore with run_adhoc_script, and once the code has proven itself, save it under a `scripts/` folder and run it by path from then on. The output format is identical to run_script.

## agent

Manages installed agents from the registry, with four actions: `search` finds agents by id, name, description, or tags; `install` copies one into `agents/`, resolving agents it depends on; `check` compares installed agents against the registry and reports what changed on each side; `update` pulls upstream changes while keeping local modifications (files changed on both sides get the upstream version written as `<file>.new` next to yours).
