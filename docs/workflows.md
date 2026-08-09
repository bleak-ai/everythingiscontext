# Workflows

A context-based workflow is a module with a fixed shape. Every workflow lives in `modules/` as a module, but not every module is a workflow: a module is any folder of files that holds accumulated knowledge on a topic; a workflow is a module that follows the specific structure defined here (frontmatter manifest, steps/, runs/). It is a series of steps the agent executes with judgment, where every run leaves a persistent trace on disk. The workflow remembers what happened last run, accumulates knowledge, and gets better over time. A skill or prompt runs and forgets; a workflow holds state.

This document is the template spec: the contract a workflow folder must follow to be distributable. The CLI (`gcontext add`), the site directory, and the authoring tooling all build against it. It is one standard for all workflows; there are no per-domain variants.

## Folder anatomy

```
<workflow-id>/
  index.md            # required: frontmatter manifest + objective, parameters, context
  steps/              # required: the procedure
    index.md          #   map: one line per step
    0-preflight.md    #   numbered step files, executed in order
    1-init.md
    ...
  commands/           # required: entry points
    setup.md          #   required: the install interview (see setup contract)
    start-workflow.md #   optional: the run driver, added when it earns its place
  functions/          # optional: per-step helper library
    2-transform/
      index.md        #   which helper applies to which case (the switch)
      from-x.md
      from-y.md
  runs/               # one folder per run
    example/          #   ships with the template: a fabricated run (see example run)
    2026-08-07/       #   the user's own runs, generated locally, never shared
```

The only code-enforced requirement is `index.md` with valid frontmatter. Everything else is convention: step files state what they need from previous steps in prose; nothing checks it mechanically. The process is AI-driven, so requirements live in the text the agent reads, not in validation code.

## Manifest: frontmatter in index.md

The manifest is YAML frontmatter at the top of the workflow's `index.md`. There is no separate manifest file, and no version field: installs are snapshots, and a version mechanism comes only when updates exist.

```yaml
---
id: coolify-ops              # unique, url-safe slug; the argument to `gcontext add`
                             # and the site path /workflows/<id>
name: Coolify Ops            # human display name, shown in the directory
description: >               # one or two sentences; the directory card text
  Mirror of a Coolify instance with operational playbooks that
  accumulate as incidents are resolved.
parameters:                  # what a run starts with; bound at setup or per run
  - name: instance-url
    description: Base URL of the instance to operate
    required: true
  - name: scope
    description: Limit operations to one project
    required: false
connections:                 # service capabilities the workflow needs
  - kind: http-api           # generic kind, not a product name
    description: The hosting panel API (Coolify, Dokploy, or similar)
tags: [ops, infrastructure]  # directory filtering
---
```

Field notes:

- `id` is the identity everywhere: the install argument, the folder name, the site slug. Lowercase letters, digits, hyphens.
- `name` is the display name for the directory and the workflow page; the id stays the machine identity.
- `parameters` are slots, not values. The setup interview or the run start binds them. Never ship bound values.
- `connections` entries are structured (`kind` plus `description`) so the site can render them as requirement badges. They name capability kinds, not products. The body of `index.md` may mention concrete services as examples; the steps must not depend on one (see docs/modules.md on connection-agnostic modules). The agent maps kinds to its own `connections/` at run time.
- `tags` is a flat list for the directory. Keep it short.

After the frontmatter, the body of `index.md` carries: the objective in the first paragraph, what each parameter means in practice, the workflow's run naming scheme (see runs/), and the general context the agent needs across all steps. Context specific to one step belongs in that step's file.

## steps/

`steps/index.md` is the map: one line per step, in order. Each step is one numbered file (`0-preflight.md`, `1-init.md`, ...). Number from 0 when there is a gate or check before real work starts.

Each step file states:

- **Purpose**: what this step achieves and why it exists.
- **Input**: what it needs, and from where (parameters, a previous step's results file, a connection).
- **Output**: what it writes into the run folder, with the schema when the output is tabular (column list for a CSV, field list for JSON).
- **How to execute**: the procedure, in enough detail that an agent without prior context can do it. Include known blockers and how to classify or route them.
- **Done when**: the condition that closes the step.

Steps that pause for the user (approval, manual action, batching) say so explicitly: what to present, what to wait for.

## runs/

Every execution of the workflow is one folder in `runs/`.

**The run folder name is workflow-defined.** Each workflow states its own run naming scheme in its `index.md`: whatever identifies one run in that domain. A gym migration names runs by gym id, an invoicing workflow by plant and period, a research pipeline by batch name. The ISO date (`2026-08-07`; second run the same day `2026-08-07-b`) is only the default for workflows with no better key. The run name should carry meaning; the date is the fallback.

Inside a run folder:

```
runs/<run-key>/
  index.md           # map and status: scope of the run, per-step status table
  0-parameters.csv   # the parameters this run started with (.csv, .json, or .md)
  1-init/
    results.csv      # the step's output, schema per the step file
    script.py        # optional: a generated script saved to avoid regenerating it
  2-transform/
    results.json
  done/
    info.md          # written when the run closes: what was achieved, what was learned
```

Conventions:

- `0-parameters.*` records what the run started with, always, even when trivial. It is what makes a run reproducible and auditable.
- One folder per executed step, named like the step file without the extension. Its main artifact is `results.*`. When the agent generated code worth keeping, it saves the script next to the results.
- The run's `index.md` is the resume point: a session picking up a half-finished run reads it and continues from the first step that is not done.
- `done/` closes the run: `info.md` summarizes what was achieved and anything learned that should change the steps, plus any final deliverable files. A run without `done/` is open.
- Learnings that outlive the run (a new blocker type, a better procedure) get folded back into the step files or `functions/`. That is how the workflow improves with use.

## functions/ (optional)

Some steps do the same transformation from ever-varying inputs. `functions/` is a mini library the agent picks from, organized per step: `functions/<step>/index.md` describes the cases (the switch), one file per case describes the procedure or code for it. The step file points to its functions folder. Add `functions/` only when a step has proven to need it; most workflows ship without it.

## What ships vs what is generated

A workflow is distributed as a template. The template is the procedure plus one fabricated demonstration; the state is born empty on the user's machine.

Ships in the template:

- `index.md` with the frontmatter manifest
- `steps/`
- `commands/setup.md` (and any other generic commands)
- `functions/` when the workflow has them
- `runs/example/`: the example run

Never ships, generated locally at setup and use:

- the user's own run folders in `runs/`
- every personalized file: configs, credentials references, scripts bound to the user's systems, playbooks learned from the user's own work

Installs are snapshots. The user's copy is theirs: personalized, growing, never overwritten by an update. `gcontext add` on an existing module warns and stops instead of overwriting.

## The example run

Every template ships one fabricated run at `runs/example/`, in the exact `runs/` shape: `index.md`, `0-parameters.*`, one folder per step with plausible results, `done/info.md`. All names and data in it are fake, made up by the author; it must contain nothing personal.

The example run has two jobs:

- On the site, it is the centerpiece of the workflow's page: the visitor browses it file by file and sees exactly what each step produces before installing anything.
- In the installed folder, it is the reference: the agent reads it to see what a correct run looks like before executing its first real one.

The folder name `example` (instead of a run key) is what marks it fabricated. The setup command leaves it in place.

## The setup command contract

`commands/setup.md` is the bridge from template to personal instance. It is an interview: the agent asks, the user answers in plain words, the agent builds and confirms. The contract:

1. **Read first**: the command starts by instructing the agent to read the workflow's `index.md` and `steps/index.md` so the interview is informed.
2. **Bind every parameter slot**: ask for each manifest parameter that is bound at setup time (per-run parameters are only explained, not bound).
3. **Map connections**: for each `connections` entry, find a matching service in the agent's environment or help the user create one. In gcontext that means `connections/`; standalone it means whatever access the user's agent has.
4. **Generate the personal state**: create the files this workflow needs locally (config, scripts against the user's systems, an empty runs/ besides the example). What gets generated is listed in the setup command itself.
5. **Smoke test**: verify the critical path (a read against the user's system, a dry run of the first step) before declaring setup done.
6. **Never rewrite the procedure**: setup personalizes state; it does not edit `steps/`.

The same file must work on both install paths:

- **In gcontext**: `commands/setup.md` carries the standard command frontmatter (`description`, optional `parameters`), so the server exposes it as an MCP prompt and the user runs it as a slash command.
- **Standalone**: the user downloads the plain folder, opens any agent in it, and says "run the setup in commands/setup.md". The agent reads the file and executes the same interview. Therefore the body must be self-contained prose that assumes only file access, not gcontext tools.

## Sharing a workflow

Authors turn a lived workflow into a template with the share-workflow instructions: docs/share-workflow.md. It strips the personal specifics into parameter slots and connection requirements, generates the setup command, fabricates the example run, and verifies the result against this spec.

## Relation to modules

A workflow is a module (see docs/modules.md): installed into `modules/`, connection-agnostic, growing with use. The workflow spec adds the fixed shape on top: manifest frontmatter, `steps/`, `runs/`, the setup contract, the example run. Everything modules.md says about growth and portability applies unchanged.
