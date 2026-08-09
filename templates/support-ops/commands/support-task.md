---
description: Resolve a support ticket end to end. Takes a ticket ID or "next" to pull from the queue.
parameters:
  - name: ticket
    description: The ticket ID to resolve (e.g. "TICKET-42") or "next" for the top unassigned ticket
    required: true
---

# Support Task

Read this workflow's `index.md` and `steps/index.md` to load the full procedure.

Resolve the ticket `$ticket` by executing steps 0 through 5 in order:

0. **Intake**: fetch the ticket, identify the customer and category, set it to in progress.
1. **Plan**: find a matching playbook or propose a custom plan. Stop for approval.
2. **Execute**: run the plan step by step. Reads execute immediately. For every write, present what/command/impact and wait for explicit approval.
3. **Log**: write the structured run folder with intake, plan, execution log, and outcome.
4. **Learn**: create or update a playbook with what was learned.
5. **Close**: post the resolution comment and close the ticket. Both need approval.

Narrate each step as you go. Before any write to an external system, describe what you are about to do and stop for approval.
