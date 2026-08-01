# Modules

Modules are portable, shareable units of context that anyone can drop into an agent folder. A module is a folder of files that teaches an agent how to do something. It works with whatever connections the agent already has.

## What a module is

A module is a folder inside `modules/`. The only requirement is an `index.md` that explains what the module does. Everything else depends on what the module is for.

A module does NOT contain code, API keys, or connection config. It contains knowledge, processes, and structure. The agent uses the module's instructions together with whatever connections are available in the folder.

## Why this works

Modules are connection-agnostic. A support workflow module doesn't know about Stripe or Postgres. It knows "intake a ticket, find the right playbook, execute with approval, log the result." The agent figures out which connections to use at runtime by reading `connections/`.

This means the same module works for:
- A company using Stripe + Cloudflare
- A company using Postgres + AWS
- A company using Linear + Firestore

The module provides the process. The connections provide the capabilities. The playbooks (built over time) provide the company-specific knowledge.

## Structure

Minimal module:
```
modules/my-module/
  index.md            # required: what this is, how it works
```

Workflow module (like support-workflow):
```
modules/support-workflow/
  index.md            # what this is, how the agent should use it
  steps.md            # the process to follow
  playbooks/          # reusable procedures, built over time
  logs/               # execution records, accumulated over time
```

Knowledge module (just information):
```
modules/company/
  index.md            # overview
  team.md             # who does what
  infrastructure.md   # how things are deployed
```

There is no enforced schema beyond `index.md`. Different modules have different structures depending on what they do. When `index.md` gets long, split it into more files and link them from `index.md`.

## How someone uses a module

1. Download the module folder (or copy it)
2. Drop it into `modules/` in your agent folder
3. That's it. The agent discovers it via `overview()` and can read all its files.

No installation step, no config to edit, no dependencies to resolve. It's just files.

## How the agent interacts with a module

The agent sees modules listed in `overview()`. When a task matches a module's purpose, the agent:

1. Reads `index.md` to understand what the module does
2. Reads any additional files (steps, playbooks, references)
3. Checks `connections/` for available services
4. Executes using `run_script` with the folder's secrets
5. Writes back to the module (new playbooks, logs) if the module's process calls for it

The module grows over time as the agent adds playbooks and logs. Each copy diverges from the original as it accumulates specific knowledge. When a module stops being relevant, move it to `archive/modules/`.

## What makes a good module

- **`index.md` is self-contained.** Anyone reading it (human or agent) should understand the module's purpose in the first paragraph.
- **Connection-agnostic.** Never reference specific services by name in the workflow steps. Say "the payment provider" not "Stripe."
- **Process over implementation.** Describe what to do, not how to call a specific API. The connection's `index.md` handles the API details.
- **Grows with use.** Playbooks and logs are empty when downloaded. They fill up as the agent works.

## Examples

**Support workflow**: a 5-step process for resolving support tickets. Ships with the process and empty playbooks. The agent builds playbooks as it resolves real issues for your company.

**Onboarding workflow**: a checklist for setting up new team members. Ships with the steps. Each company customizes it with their specific accounts, tools, and access requirements.

**Incident response**: a process for handling production incidents. Ships with severity levels and communication templates. Playbooks accumulate as incidents are resolved.

**SEO pipeline**: a content creation workflow. Ships with the process (research, write, review, publish). Adapts to whatever CMS and analytics connections the company has.
