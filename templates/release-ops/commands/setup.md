---
description: Set up release-ops for your project. Maps your source control, registry, and notification connections, detects your stack, and verifies access.
---

# Setup

Read this workflow's `index.md` and `steps/index.md` first to understand what release-ops does and what it needs.

## 1. Detect the project stack

Scan the repository root for version files and build tools:

- `pyproject.toml` with `[project]` or `[tool.poetry]`: Python project. Build with `uv build`, publish with `uv publish`.
- `package.json`: Node project. Build with `npm pack`, publish with `npm publish`.
- `Cargo.toml`: Rust project. Build and publish with `cargo publish`.
- `setup.cfg` or `setup.py`: legacy Python. Note it and ask the user for their preferred build tool.
- Other: ask the user what build and publish commands to use.

Record the detected stack, version file paths, build command, and publish command. Present the detection to the user for confirmation.

## 2. Bind source control

Ask the user which git host they use (GitHub, GitLab, Bitbucket, or other). Find the matching connection in the agent's environment, or help the user create one.

Verify access: query the remote for the repository's recent tags. Present one tag as proof.

## 3. Map the package registry (optional)

Ask the user if this project is published to a package registry. If yes, identify the registry and find the matching connection.

Verify access: run a dry auth check against the registry (e.g. `uv publish --check`, `npm whoami`). If the user says there is no registry, record "no registry" and the publish step will be skipped during runs.

## 4. Map the notification sink (optional)

Ask the user if they want release announcements posted somewhere (Slack, Discord, email, or other). If yes, find the matching connection and ask which channel or recipient to use.

If the user does not want announcements, record "no notification sink" and the announce step will be skipped during runs.

## 5. Configure the test command (optional)

Ask the user if they want the preflight step to run a test suite before each release. If yes, record the test command (e.g. `uv run pytest`, `npm test`, `cargo test`).

If not, preflight will only check git and registry state.

## 6. Create the release history

Create `releases/log.md` if it does not exist:

```markdown
# Release History

| Version | Date | Summary | Notes |
|---------|------|---------|-------|
```

Create `releases/insights.md` if it does not exist:

```markdown
# Release Insights

This file is updated automatically after each release run.

## Commit style

Not yet detected. Will be set after the first run.

## Known issues

None recorded yet.

## Changelog style

Not yet detected. Will be learned from existing changelog or first approved draft.
```

## 7. Smoke test

Run a dry preflight:

1. Check that the working tree is clean.
2. Find the most recent version tag.
3. List the commits since that tag (limit to 5).
4. Present the summary.

Do not make any changes. This is read-only.

If the smoke test passes, report setup complete. If it fails, diagnose and fix before declaring done.

## What setup creates

- `releases/log.md` (empty release history table)
- `releases/insights.md` (empty insights, populated after first run)
- Nothing else. The example run and step files ship with the template.
