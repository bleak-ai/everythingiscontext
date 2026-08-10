# Connections

A connection gives the agent access to one service. It is one folder under
`connections/`, and it needs at most three things:

    connections/github/
      connection.yaml    what the connection needs, by name
      index.md           how the API works in practice
      scripts/           procedures that already worked

The agent normally writes all of this itself through the setup prompt. This
page is the reference for when you want to write or review one by hand.

## connection.yaml

The manifest declares what the connection needs. All fields:

```yaml
name: github                  # folder name, lowercase
description: GitHub REST API - repos, issues, pull requests
secrets:                      # secret NAMES only, never values
  - GITHUB_TOKEN
deps:                         # Python packages the scripts import
  - requests
```

`secrets` lists names. The values live in `secrets.env` at the folder root,
one `NAME=value` per line, gitignored. The server reads `secrets.env` live,
so adding a value needs no restart. When a script runs, the server injects
the values as environment variables and scrubs them from the output, so they
never enter the context window. `gcontext status` shows which declared
secrets have values.

`deps` are installed into the project's virtual environment on demand (via
uv) when a script needs them. Prefer plain HTTPS with `requests` over a service
SDK unless the SDK genuinely helps; one dependency that covers every
endpoint beats a heavy client library.

## index.md

The agent reads `index.md` before writing any script against the service.
Write what a fresh session needs to use the API, not marketing:

- what the service is used for in this agent
- base URL and auth style: which header, which token type
- the endpoints that matter for what this agent does
- gotchas learned in practice: rate limits, response shapes, error formats

Keep it current: when a script run teaches something (an endpoint quirk, a
pagination rule), record it in `index.md` right away. The file is the
connection's accumulated experience.

A complete example lives at
[examples/ops-agent/connections/stripe](../examples/ops-agent/connections/stripe):
a manifest, and an `index.md` with auth, gotchas, and patterns recorded from
real use.

## scripts/

Proven procedures. When a call works, save it as a script so the next
session runs it by path with `run_script` instead of rewriting it. The first
script of every connection should be the smoke test that proved it.

## Smoke test

Before trusting a new connection, verify it end to end with
`run_adhoc_script`:

1. Check the secret is injected: `os.environ.get("GITHUB_TOKEN")` is set.
   Print present or missing, never the value.
2. Make one harmless authenticated call: whoami, list, or similar.
3. If it fails: check the value is in `secrets.env` (no restart needed),
   then the header format, then the base URL.
4. When it works, save it under `scripts/` and note in `index.md` anything
   the test taught you.

## Common auth shapes

Most APIs fit one of these:

```python
# Bearer token (GitHub, Linear, most SaaS APIs)
headers = {"Authorization": f"Bearer {os.environ['SERVICE_TOKEN']}"}

# API key header (Stripe-style: key as the user in basic auth, or a
# custom header like X-Api-Key)
headers = {"X-Api-Key": os.environ["SERVICE_API_KEY"]}

# DSN in one secret (databases)
conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
```

When a service offers several auth models (personal token vs OAuth app,
cloud vs self-hosted), pick the simplest one that covers the agent's job;
that is almost always a personal token.

## Starter manifests

Copy, adjust, and add the secret value to `secrets.env`.

```yaml
# connections/github/connection.yaml
name: github
description: GitHub REST API - repos, issues, pull requests
secrets:
  - GITHUB_TOKEN
deps:
  - requests
```

```yaml
# connections/linear/connection.yaml
name: linear
description: Linear GraphQL API - issues, projects, cycles
secrets:
  - LINEAR_API_KEY
deps:
  - requests
```

```yaml
# connections/postgres/connection.yaml
name: postgres
description: Main Postgres database
secrets:
  - POSTGRES_DSN
deps:
  - psycopg2-binary
```

```yaml
# connections/<service>/connection.yaml - the generic shape
name: my-service
description: <what this service does for the agent>
secrets:
  - MY_SERVICE_API_KEY
deps:
  - requests
```
