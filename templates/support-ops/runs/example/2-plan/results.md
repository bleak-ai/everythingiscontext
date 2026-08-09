# Plan: HELP-307

- **Playbook**: swap-subscription.md (exact match on category)

## Steps

1. Fetch Elena's account (acc_8291) and confirm the active subscription. Service: product database. Permission: Read.
2. Fetch Maria's account (acc_8294) and check for existing subscriptions. Service: product database. Permission: Read.
3. Update sub_4455 to point to acc_8294. Service: product database. Permission: Write.
4. Verify: re-fetch both accounts and confirm the swap. Service: product database. Permission: Read.
5. Update the payment provider customer record to reflect the new account association. Service: payment provider. Permission: Write.

## Risks

- Maria may already have a subscription. If so, stop and ask Elena which one to keep.
- The payment method is on Elena's card. Confirm with Elena whether the same card should keep paying.
