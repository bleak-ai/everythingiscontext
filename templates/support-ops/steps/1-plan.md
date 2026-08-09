# Step 1: Plan

## Purpose

Decide how to resolve the ticket. Use an existing playbook if one matches; otherwise propose a custom plan.

## Input

- The intake file from step 0: category, customer, summary.
- `playbooks/`: the accumulated playbook library.
- `playbooks/_index.md`: the index and integration mapping.

## Output

`runs/{ticket-id}-{slug}/2-plan.md` with:

- **Playbook**: which playbook matched (file name), or "custom plan" if none.
- **Steps**: the numbered steps to execute, each naming which connection or service to use and whether it reads or writes.
- **Risks**: anything that could go wrong, and how to check.

## How to execute

1. Read `playbooks/_index.md` to get the playbook index.
2. Search for a playbook that matches the issue category. Check the "When to Use" section of candidate playbooks.
3. If a playbook matches: read it fully, adapt its steps to this specific ticket (fill in the customer, the specific IDs). Present the plan to the human.
4. If no playbook matches: propose a custom step-by-step plan. For each step, name which connection to use and whether the operation is a read or a write. Present the plan to the human.
5. Wait for the human to approve, modify, or reject the plan.

## Done when

The human has approved the plan and the plan file is written.
