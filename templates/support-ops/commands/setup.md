---
description: Set up support-ops for your team. Maps your ticket tracker and product connections, creates the playbook structure, and verifies access.
---

# Setup

Read this workflow's `index.md` and `steps/index.md` first to understand what support-ops does and what it needs.

## 1. Bind the ticket tracker

Ask the user which issue tracker they use for support tickets (Linear, Jira, GitHub Issues, or another). Find the matching connection in the agent's environment, or help the user create one.

Verify access: query the tracker for recent tickets to confirm the connection works. Present one ticket title as proof.

## 2. Map the product connections

Ask the user which systems their support team operates on. These are the services where fixes happen: a database, a payment provider, an admin API, etc. There can be one or many.

For each service, find the matching connection in the agent's environment. Record each one with its read/write permission level.

## 3. Create the playbook structure

Create `playbooks/_index.md` if it does not exist. This file serves as:

- The index of all playbooks (updated as new ones are created by step 4).
- The integration mapping: how the generic playbook steps map to the user's specific connections. For each connection mapped in the previous step, write one line explaining which playbook references (e.g. "the payment provider") map to which connection.

The two example playbooks (`swap-subscription.md` and `export-member-list.md`) ship with the template. Leave them in place as format references.

## 4. Smoke test

Run a dry intake on one real ticket:

1. Query the tracker for the most recent ticket.
2. Fetch its details.
3. Identify the customer (or confirm the product connection can look them up).
4. Present the intake summary.

Do not change any ticket status or write to the product systems. This is read-only.

If the smoke test passes, report setup complete. If it fails, diagnose and fix the connection before declaring done.

## What setup creates

- `playbooks/_index.md` (the index and integration mapping)
- Nothing else. The example playbooks and the runs/example/ folder ship with the template. Real runs and real playbooks are created during use.
