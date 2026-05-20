# Module Features — Optional Capabilities

A module is just a folder. Beyond `module.yaml` + `llms.txt` + the kind's starter file (info.md / brief.md / steps.md), a module can optionally carry:

## Scripts

Plain Python files inside the module that the agent can run on demand. The canonical example is `verify.py` — a quick sanity check that the integration's credentials and network access work.

When to add one: when the module benefits from a repeatable check, fetch, or transformation that the user (or another turn) will want to invoke later.
