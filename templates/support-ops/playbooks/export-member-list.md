# Export Member List

Export a list of active members for a given account, group, or organization.

## When to Use

A customer or internal team requests a list of members: names, emails, join dates, or subscription status. Common triggers: compliance requests, migration preparation, or account audits.

## Prerequisites

- The ticket must identify the scope: which account, group, or organization to export from.
- Confirm the scope exists in the product database.

## Steps

1. **Identify the scope.** Service: product database. Permission: Read. Look up the account or group. Record its ID and the expected member count if available.

2. **Query the members.** Service: product database. Permission: Read. Fetch all active members within the scope. Collect: name, email, join date, subscription status, and any other fields the ticket requests.

3. **Format the export.** No service needed. Format the data as a CSV or markdown table. Present the first few rows to the human for confirmation that the columns and data look correct.

4. **Deliver the export.** Post the export file or table as a comment on the ticket, or attach it per the team's standard delivery method.

## Common Variations

- The customer requests inactive members too; add a status filter toggle.
- The export includes payment history; join with the payment provider data.
- GDPR or privacy constraints limit which fields can be included; check with the human.

## Notes

- Member exports are read-only. No writes to any system.
- If the member count is large (hundreds or more), confirm with the human before posting the full list as a ticket comment. A file attachment may be more appropriate.
