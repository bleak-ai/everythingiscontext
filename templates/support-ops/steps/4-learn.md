# Step 4: Learn

## Purpose

Feed what was learned back into the playbook library so future tickets of the same type are resolved faster.

## Input

- The plan file (step 1): which playbook was used, or "custom plan".
- The execution log (step 2): what actually happened vs. what was planned.
- `playbooks/`: the current library.

## Output

One of:

- A new playbook file in `playbooks/{category-slug}.md` if no playbook existed.
- An updated playbook with new variations or notes if one existed but the execution diverged.
- No change if the execution matched the playbook exactly.

Updated `playbooks/_index.md` if a new playbook was created.

## How to execute

1. **No playbook existed**: create one at `playbooks/{category-slug}.md` using the standard playbook format (see `playbooks/_index.md`). Generalize the steps: replace specific customer names and IDs with placeholders. Keep the procedure concrete enough that the agent can follow it on a future ticket.
2. **Playbook existed, execution diverged**: compare the plan to the execution log. Add new variations to the "Common Variations" section. Add new warnings or edge cases to "Notes". Do not remove existing content.
3. **Playbook existed, execution matched**: report "matched" and move on. No file changes.
4. Present what was created or changed to the human for review.

## Done when

The playbook library reflects what was learned from this ticket. If a new playbook was created, `playbooks/_index.md` lists it.
