# 0 - Preflight

## Purpose

Verify that the repository is in a releasable state before any work starts. Catch problems early so the release does not fail midway.

## Input

- The repository's current git state.
- The `scope` parameter (if set, check only the scoped package).
- `releases/insights.md` (if it exists): known-flaky checks and past blockers.
- The test command recorded during setup (if any).

## Output

Write `0-preflight.md` in the run folder with a checklist of every check and its result (pass/fail/skip).

## How to execute

Run these checks in order. Stop on the first failure and report it.

1. **Working tree is clean.** No uncommitted changes. If dirty, list the changed files and stop.
2. **Branch is up to date.** The current branch has no unpushed commits and is not behind the remote. Pull if behind; stop if there are conflicts.
3. **Last release tag exists.** Find the most recent tag that looks like a version (v*, semver). If no tag exists, treat the entire history as "changes since the beginning" and note this in the checklist.
4. **Registry auth works** (skip if no registry configured). Run a dry authentication check against the package registry. Method depends on the stack (e.g. `uv publish --check` for PyPI, `npm whoami` for npm). If auth fails, stop and report.
5. **Test suite passes** (skip if no test command configured). Run the test command recorded during setup. If tests fail, list the failures and stop.
6. **Known-issue scan.** If `releases/insights.md` exists, check for any known blockers or flaky tests relevant to this release. Warn the user if any match.

## Done when

All checks pass (or are skipped with a reason). The preflight checklist is written to the run folder.
