# Step 0: Intake

## Purpose

Accept a ticket and gather all the information needed to plan the resolution. Set the ticket to "in progress" so the team knows it is being handled.

## Input

- `ticket-id` parameter: a ticket identifier or "next".
- The ticket tracker connection: to fetch ticket details and update status.

## Output

`runs/{ticket-id}-{slug}/1-intake.md` with:

- **Ticket**: ID, title, priority, labels, link.
- **Reporter**: who filed it and when.
- **Customer**: the affected customer or account (identified from the ticket or looked up in the product).
- **Category**: the issue type (e.g. "billing-sync", "access-issue", "data-export").
- **Slug**: a short kebab-case description derived from the title.
- **Summary**: one paragraph restating the problem in plain words.

## How to execute

1. If `ticket-id` is "next", query the ticket tracker for the highest-priority unassigned ticket. Present it and wait for confirmation before proceeding.
2. Fetch the full ticket: title, description, priority, labels, all comments.
3. Identify the customer. The ticket may name them directly; if not, look them up in the product systems.
4. Classify the issue into a category slug. Check if `playbooks/` has a file that matches.
5. Set the ticket status to "in progress" in the tracker. This is the only write that does not need human approval.
6. Present the intake summary to the human.

## Done when

The intake file is written and the human has confirmed the summary is correct.
