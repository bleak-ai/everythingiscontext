# Stripe

Stripe is our payment processor. All billing operations go through the Stripe API.

## Authentication

Use the `stripe` Python library. The API key is injected as an environment variable:

```python
import stripe
import os

stripe.api_key = os.environ["STRIPE_API_KEY"]
```

## Gotchas

### Stripe objects use attribute access, not dict access

Stripe API objects (Account, Charge, Customer, etc.) are NOT plain dicts. Do NOT use `.get()` on them. Use dot-notation attribute access instead.

```python
# WRONG - raises AttributeError
account.get("settings", {}).get("dashboard", {})

# CORRECT - use attribute access
account.settings.dashboard.display_name
account.business_profile.name
```

For nested fields that might be None, check the parent first:

```python
display_name = account.settings.dashboard.display_name if account.settings else None
```

## Common operations

### List recent charges

```python
import stripe, os
stripe.api_key = os.environ["STRIPE_API_KEY"]

charges = stripe.Charge.list(limit=10)
for charge in charges.data:
    print(f"{charge.id}: {charge.amount/100:.2f} {charge.currency} - {charge.status}")
```

### Issue a refund

```python
import stripe, os
stripe.api_key = os.environ["STRIPE_API_KEY"]

refund = stripe.Refund.create(charge="ch_xxx")
print(f"Refund {refund.id}: {refund.status}")
```

### List customers

```python
import stripe, os
stripe.api_key = os.environ["STRIPE_API_KEY"]

customers = stripe.Customer.list(limit=20)
for c in customers.data:
    print(f"{c.id}: {c.email} - {c.name}")
```

### Create a subscription

```python
import stripe, os
stripe.api_key = os.environ["STRIPE_API_KEY"]

subscription = stripe.Subscription.create(
    customer="cus_xxx",
    items=[{"price": "price_xxx"}],
)
print(f"Subscription {subscription.id}: {subscription.status}")
```

## Webhook handling

The webhook secret is `STRIPE_WEBHOOK_SECRET`. Use it to verify webhook signatures:

```python
import stripe, os

payload = "..."  # raw request body
sig_header = "..."  # Stripe-Signature header
endpoint_secret = os.environ["STRIPE_WEBHOOK_SECRET"]

event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
print(f"Event: {event.type}")
```

## API reference

- Full docs: https://stripe.com/docs/api
- Python library: https://github.com/stripe/stripe-python
- Dashboard: https://dashboard.stripe.com
