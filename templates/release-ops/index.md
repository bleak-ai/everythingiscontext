---
id: release-ops
name: Release Ops
description: >
  A release workflow that collects changes, drafts a changelog, bumps the
  version, publishes, and optionally announces. Each release is a searchable
  run; the workflow learns your changelog style and known blockers over time.
parameters:
  - name: version
    description: Target version (e.g. "0.5.0") or omit for agent proposal based on changes
    required: false
  - name: scope
    description: Limit to a specific package in a monorepo (e.g. "@acme/core")
    required: false
connections:
  - kind: source-control
    description: The git host where the repository lives (GitHub, GitLab, or similar)
  - kind: package-registry
    description: The registry to publish to (PyPI, npm, crates.io, or similar). Optional; skip if the project has no published package.
  - kind: notification-sink
    description: Where to post release announcements (Slack, Discord, email, or similar). Optional; skip if not needed.
tags: [release, ops, devtools]
---

Ship a release with a repeatable six-step procedure. Each run takes one release from preflight to announcement, logs the result, and feeds learnings back into future runs.

The `version` parameter accepts an explicit semver string (e.g. "1.2.0") or can be omitted. When omitted, the agent proposes major/minor/patch based on the changes collected in step 1. The agent always asks for confirmation before applying a version bump.

The `scope` parameter is for monorepos. When set, the workflow limits change collection, version bumping, and publishing to the named package. When omitted, the workflow operates on the entire repository.

Run folders are named by version: `v{version}` (e.g. `v0.5.0`). If a second release happens the same day with the same version prefix, append `-b` (e.g. `v0.5.0-b`).

## How it learns

The workflow accumulates knowledge in two ways:

1. **Release history** (`releases/log.md`): a table of every release with version, date, summary, and notes. The agent consults it to understand release cadence and past decisions.

2. **Insights** (`releases/insights.md`): created after the first run. Records the repo's changelog style (tone, grouping, detail level), known-flaky checks, common blockers, and workarounds. The agent consults this during preflight and changelog drafting.
