# Secrets

Secrets are environment variables. Modules declare which variables they need in `module.yaml` under the `secrets:` list — variable names only, never values.

## How it works

1. Check a module's `module.yaml` for its `secrets:` list
2. Values live in `.env` at the project root (gitignored, never committed)
3. `.env.example` is auto-generated with all required variable names
4. Run `eic env` to check which variables are set or missing

## Rules

- Never hardcode secret values in module files
- Never commit `.env` to version control
- Access secrets via `os.environ` in scripts
