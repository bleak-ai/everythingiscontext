# workflows API

The marketplace backend for workflow templates. A FastAPI service with a Postgres database. Templates are stored as file bundles (one row per file) plus indexed manifest fields parsed server-side from the bundle's `index.md` frontmatter (see `docs/workflows.md` for the template standard).

Publishing is submit-for-review: anyone can POST a bundle, it lands pending, and it appears publicly only after approval.

## Endpoints

- `GET /api/workflows`: approved directory (id, name, description, tags).
- `GET /api/workflows/{id}`: one approved template with its full file bundle.
- `POST /api/workflows`: submit a bundle for review. Body: `{"files": [{"path": "...", "content": "..."}]}`.
- `GET /api/moderation/workflows`: pending entries (admin token).
- `GET /api/moderation/workflows/{id}`: one pending bundle (admin token).
- `POST /api/moderation/workflows/{id}/approve`: publish (admin token). Approving an id that is already published replaces the published content.
- `POST /api/moderation/workflows/{id}/reject`: hide (admin token).

Moderation auth is a single bearer token: `Authorization: Bearer $ADMIN_TOKEN`.

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

## Seed

```
ADMIN_TOKEN=... uv run python scripts/seed.py <template-folder> --api-url https://api.gcontext.ai
```
