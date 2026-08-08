# Step 2: do the operation

## Purpose

Perform the operation this run was started for, using accumulated
playbook knowledge before investigating from scratch.

## Input

- The requested operation and its target, from `0-parameters.md` in the
  run folder.
- The synced mirror (`overview.md`), for names, uuids, statuses, and
  domains. Never call the API with a uuid that was not confirmed against
  the mirror.
- `playbooks/`: the library of procedures from previous runs.

## Output

`2-operate/results.md` in the run folder: what was done, every API call
made, what the API returned, and what surprised you. When a script was
generated and is worth keeping, save it next to the results as
`script.py`.

## How to execute

1. Check `playbooks/` first. If a playbook matches the requested
   operation, follow it before investigating from scratch.
2. If no playbook matches, investigate through read-only API calls, then
   propose the write operations to the user. Keep notes; step 3 turns
   them into a new playbook.
3. Confirm the target with the user (name plus uuid from the mirror)
   before any write call.

## Hard rules

- Never delete anything on the instance. No delete endpoints, ever.
- Ask the user before every write operation against the API (deploy,
  restart, stop, start, env changes, anything non-GET). Beware: in the
  Coolify API some write operations are GET endpoints, for example the
  deploy trigger `GET /deploy?uuid=<app_uuid>`. Classify by effect, not
  by verb.
- Read operations (GET without side effects) need no confirmation.

## Done when

The operation is completed and verified (or explicitly stopped by the
user), and `2-operate/results.md` records what happened.
