# Sync results

Ran the saved sync script against the instance. Fleet: 1 server, 2
projects, 3 applications, 1 service, 1 database.

Drift against `overview.md` since the last sync (2026-07-28):

- `application | staging-portal | pk4n8r2v6z0c3m7q1w5e9t3y` changed
  status: `running:healthy` to `exited:unhealthy`. Reported to the user;
  not this run's target, noted for a separate investigation.
- No other changes. The target `acme-website` is
  `mk3v7q9x2c5b8n1z4f6h0j2l`, status `running:unknown`, domain
  `https://acme-website.example.com`.

`overview.md` updated to match, "Last sync" set to 2026-08-02.
