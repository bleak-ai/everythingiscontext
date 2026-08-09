# Swap Subscription

Transfer an active subscription from one customer account to another within the same organization.

## When to Use

A customer has an active subscription linked to the wrong account. They need it moved to a different account, usually a family member, a renamed profile, or a duplicate that should not exist.

## Prerequisites

- The ticket must identify both accounts: the source (where the subscription is now) and the target (where it should go).
- Confirm both accounts exist in the product database before starting.

## Steps

1. **Fetch the source account.** Service: product database. Permission: Read. Look up the account and confirm the active subscription. Record the subscription ID, plan, and billing status.

2. **Fetch the target account.** Service: product database. Permission: Read. Confirm the account exists. Check if it already has an active subscription (if so, stop and report the conflict to the human).

3. **Update the subscription record.** Service: product database. Permission: Write. Change the account reference on the subscription from source to target. Present the exact change to the human before executing.

4. **Verify the swap.** Service: product database. Permission: Read. Re-fetch both accounts. Confirm the source no longer has the subscription and the target does.

5. **Update the payment provider.** Service: payment provider. Permission: Write. If the payment provider tracks account associations separately, update it to match. Present the change to the human before executing.

## Common Variations

_(This section grows from real executions. Examples of variations that may appear over time:)_

- The source account has multiple subscriptions; only one should move.
- The target account is in a different billing group or plan tier.
- The subscription is past due; the swap should preserve the past-due state, not reset it.

## Notes

- Never cancel and re-create a subscription as a shortcut for swapping. Cancellation triggers downstream effects (access revocation, email notifications) that are hard to reverse.
- Always verify after the swap. A successful database write does not guarantee the payment provider is in sync.
