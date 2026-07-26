# Cloudflare

Cloudflare manages our DNS records and CDN. We use the REST API v4 directly with `requests`.

## Authentication

Cloudflare uses an API key + email for authentication. Both are injected as environment variables:

```python
import requests, os

headers = {
    "X-Auth-Key": os.environ["CF_API_KEY"],
    "X-Auth-Email": os.environ["CF_API_EMAIL"],
    "Content-Type": "application/json",
}
base_url = "https://api.cloudflare.com/client/v4"
```

## Our zones

- `example.com` (zone ID: check via list zones script)
- `app.example.com` (proxied, orange cloud)

## Common operations

### List all zones

```python
import requests, os

headers = {
    "X-Auth-Key": os.environ["CF_API_KEY"],
    "X-Auth-Email": os.environ["CF_API_EMAIL"],
}

resp = requests.get("https://api.cloudflare.com/client/v4/zones", headers=headers)
for zone in resp.json()["result"]:
    print(f"{zone['id']}: {zone['name']} - {zone['status']}")
```

### List DNS records for a zone

```python
import requests, os

headers = {
    "X-Auth-Key": os.environ["CF_API_KEY"],
    "X-Auth-Email": os.environ["CF_API_EMAIL"],
}

zone_id = "YOUR_ZONE_ID"
resp = requests.get(
    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
    headers=headers,
)
for rec in resp.json()["result"]:
    print(f"{rec['type']:6} {rec['name']:40} -> {rec['content']}")
```

### Create a DNS record

```python
import requests, os

headers = {
    "X-Auth-Key": os.environ["CF_API_KEY"],
    "X-Auth-Email": os.environ["CF_API_EMAIL"],
    "Content-Type": "application/json",
}

zone_id = "YOUR_ZONE_ID"
resp = requests.post(
    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
    headers=headers,
    json={
        "type": "A",
        "name": "new-subdomain.example.com",
        "content": "1.2.3.4",
        "proxied": True,
    },
)
print(resp.json())
```

## API reference

- Full docs: https://developers.cloudflare.com/api/
- Dashboard: https://dash.cloudflare.com
