# Step 3: close the run

## Purpose

Turn the run into durable knowledge: close the run folder and fold what
was learned back into the playbooks. This is how the workflow improves
with use.

## Input

- The run folder so far: `0-parameters.md`, `1-sync/results.md`,
  `2-operate/results.md`.
- The playbook that was followed, if any.

## Output

- `done/info.md` in the run folder: what was achieved, what surprised
  you, and what changed in the playbooks because of this run. A run
  without `done/` is open.
- A written or improved playbook in `playbooks/`.

## How to execute

1. Update the run folder's `index.md` status table: every step's state,
   so a later session can see the run is closed.
2. Write `done/info.md`: what was asked, what was done, what the API
   returned that was unexpected, and the playbook effect.
3. Playbooks: if a playbook was followed, improve it with what this run
   taught. If the operation was investigated from scratch, write a new
   playbook from what actually happened. Playbooks record lived
   procedure, not designed procedure.

## Done when

`done/info.md` exists, the run index shows every step done, and the
playbook library reflects what this run learned.
