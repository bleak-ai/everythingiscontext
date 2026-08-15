# gcontext API

A FastAPI service with a Postgres database. It tracks agent download counts and install telemetry.

## Endpoints

### Public

- `GET /api/workflows/{id}`: returns the download count for a workflow. When `x-source: site` is set, returns the count without incrementing. Otherwise increments the counter and returns the new value.

### Telemetry

- `POST /api/telemetry`: records an install event (install_id, version, os, platform). Rate-limited to one request per second per IP. Returns 204 on success.

### Admin (requires `Authorization: Bearer $ADMIN_TOKEN`)

- `GET /api/admin/workflows`: lists all workflows ordered by download count.
- `GET /api/admin/installs`: lists the 200 most recent install events.
- `DELETE /api/admin/installs/{install_id}`: deletes an install record.

## Configuration

Env vars: `DATABASE_URL` (postgresql+psycopg://...), `ADMIN_TOKEN`. Optional: `MAX_FILE_BYTES` (default 1000000), `MAX_BUNDLE_BYTES` (default 5000000), `MAX_FILES` (default 200).

Tables are created on startup.

## Run locally

```
cd api
uv sync
DATABASE_URL=postgresql+psycopg://... ADMIN_TOKEN=dev uv run uvicorn app.main:app --reload
```

## Tests

Tests need Docker (they start a throwaway Postgres container):

```
cd api
uv run pytest
```
