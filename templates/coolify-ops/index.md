---
id: coolify-ops
name: Coolify Ops
description: >
  Operate a Coolify instance with a synced mirror of what is deployed and
  playbooks that accumulate as operations are performed and repeated.
parameters:
  - name: instance-url
    description: Base URL of the Coolify instance to operate (for example https://coolify.example.com)
    required: true
connections:
  - kind: http-api
    description: The Coolify API of the instance, authenticated with an API token
tags: [ops, infrastructure]
---

# coolify-ops

Operations workflow for a Coolify instance. It is a mirror plus playbooks
loop: a synced map of what is deployed on the instance, and playbooks for
the operations performed on it again and again. Every run starts with a
sync, so the mirror never drifts from reality, and every run ends by
writing what it learned back into the playbooks. The workflow gets better
the more operations it performs.

## Parameters in practice

- `instance-url`: the base URL of the Coolify instance, bound once at
  setup. All API calls go to `<instance-url>/api/v1`. The API token that
  authenticates the calls is stored as a secret during setup, never in
  these files.
- Each run additionally starts from one requested operation (redeploy an
  application, investigate a failing service, change an env var). The
  operation is a per-run input, recorded in the run's `0-parameters.md`,
  never bound at setup.

## Run naming

Run folders are named `<date>-<operation-slug>`, for example
`2026-08-02-redeploy-website`. The date anchors the run in time; the
operation slug says what the run did. Use the plain ISO date only if a run
has no single nameable operation.

## Files

- `steps/`: the loop, executed in order on every run. Read
  `steps/index.md` first.
- `playbooks/`: one file per recurring operation, written from real runs.
  Ships with one seed playbook (redeploy an application); grows with use.
- `runs/`: one folder per run. `runs/example/` is a fabricated
  demonstration run with fake names; read it before the first real run.
- `commands/setup.md`: the install interview. Run it once before the
  first run.
- `overview.md` (created at setup): the mirror, the synced state of the
  instance. Not part of the template; every install builds its own.

## Hard rules

- Never delete anything on the instance. No delete endpoints, ever.
- Ask the user before every operation that changes the instance (deploy,
  restart, stop, start, env changes). Classify by effect, not by HTTP
  verb: the Coolify deploy trigger is a GET that writes.
- Read operations (GET without side effects) need no confirmation.
