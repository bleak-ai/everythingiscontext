# Infrastructure

## Hosting

- **Hetzner VPS**: main server, runs all production services via Coolify
- **Cloudflare**: DNS, CDN, TLS termination for all domains
- **GitHub**: code hosting, CI/CD via GitHub Actions

## Domains

- `example.com`: main website
- `app.example.com`: SaaS application
- `api.example.com`: API endpoint

## Deployment

All services deploy via Coolify on the Hetzner VPS. Docker images are built from GHCR. Deployments are triggered by pushes to the main branch.
