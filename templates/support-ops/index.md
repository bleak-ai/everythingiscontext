---
id: support-ops
name: Support Ops
description: >
  A support workflow that resolves tickets, logs every action, and builds
  playbooks from experience. Each resolved ticket becomes a searchable record;
  repeated patterns become reusable playbooks the agent consults on future tickets.
parameters:
  - name: ticket-id
    description: The ticket to resolve (e.g. "TICKET-42") or "next" to pull the top item from the queue
    required: true
connections:
  - kind: ticket-tracker
    description: The issue tracker where support tickets live (Linear, Jira, GitHub Issues, or similar)
  - kind: product-api
    description: The product's own API or database, for executing fixes (one or more services the team operates on)
tags: [support, ops]
---

Resolve support tickets with a repeatable six-step procedure. Each run takes one ticket from intake to close, logs every operation performed, and feeds what was learned back into playbooks for future tickets.

The `ticket-id` parameter accepts a ticket identifier from the tracker (e.g. "TICKET-42", "HELP-108") or the keyword "next" to pull the highest-priority unassigned ticket from the queue.

Run folders are named by ticket: `{ticket-id}-{slug}` where the slug is a short description of the issue (e.g. `TICKET-42-swap-membership`). The agent derives the slug from the ticket title during intake.

## How it learns

The workflow accumulates knowledge in two ways:

1. **Playbooks** (`playbooks/`): generalized procedures for recurring issue types. Step 1 (plan) consults them; step 4 (learn) creates or updates them. A new install starts with two example playbooks to show the format. Real playbooks grow from the team's own ticket history.

2. **Run history** (`runs/`): every resolved ticket is a structured folder with intake, plan, execution log, and outcome. The agent can search past runs to find how a similar issue was handled before.

## Playbook format

Each playbook in `playbooks/` follows a standard structure: When to Use, Prerequisites, Steps (each with Service, Permission level, and procedure), Common Variations (added over time from real executions), and Notes. See `playbooks/_index.md` for details and the example playbooks for the format.
