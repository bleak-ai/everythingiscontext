# Principles — Modifying Context

These are the rules for creating, editing, or extending modules.

## Module locations

Modules live at `modules-repo/<slug>/`. The `context/` directory contains symlinks for the subset of modules currently loaded into the active workspace — **it is a view, not a storage location.**

Two operations that look similar but are NOT the same:

- **Create / edit a module.** You write files at `modules-repo/<slug>/...`. This is the only kind of write you perform.
- **Load a module into the workspace.** This creates a symlink inside `context/`. It is managed by `eic.py`, not by you.

Each module is a folder with at least `module.yaml` and `llms.txt`.

## Reading context before modifying

Before answering anything that references or implies a topic likely covered by an existing module, read that module's `llms.txt` first. If `llms.txt` declares a `## Where to write` section, that section governs where any subsequent appends go (path, naming pattern, template). Do NOT invent a new location.

If no module matches, you may answer from general knowledge — but if the conversation produces durable content (a finding, a note worth keeping, a new procedure), propose a new module rather than silently dropping it.

## Module schema and kinds

See [structure.md](structure.md) for the authoritative module.yaml schema and the per-kind file layout (integration / task / workflow). That file is auto-generated from code — read it; do not invent fields.

## When to propose a new module vs append to an existing one

- **Append** when the content is one more instance of a pattern the module already tracks (another note, another run, another finding).
- **New module** when the content concerns a different external service, a different task with its own goal, or a different repeatable procedure. New modules cost almost nothing — favor a small new module over stretching an existing one.
