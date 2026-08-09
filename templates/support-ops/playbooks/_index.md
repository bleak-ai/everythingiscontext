# Playbooks

Reusable procedures for recurring support issue types. The agent consults this index during step 1 (plan) to find a matching playbook. Step 4 (learn) creates new playbooks or updates existing ones after each resolved ticket.

## Playbook format

Each playbook file follows this structure:

- **Title**: one-line description of what the playbook resolves.
- **When to Use**: the trigger conditions that indicate this playbook applies.
- **Prerequisites**: what information is needed before starting.
- **Steps**: numbered, each with Service (which connection), Permission (Read or Write), and the procedure.
- **Common Variations**: edge cases and alternative paths discovered from real executions. This section grows over time.
- **Notes**: warnings, API quirks, safety checks learned from experience.

## Integration mapping

This section maps generic playbook references to the actual connections in this agent's environment. Fill it in during setup.

- "the ticket tracker" maps to: _(fill during setup)_
- "the product database" maps to: _(fill during setup)_
- "the payment provider" maps to: _(fill during setup)_

## Index

- [swap-subscription.md](swap-subscription.md): transfer a subscription between two customer accounts.
- [export-member-list.md](export-member-list.md): export a list of active members for a given account or group.
