# 2 - Changelog

## Purpose

Draft a changelog entry from the collected changes. The draft matches the repo's existing changelog style when possible.

## Input

- `1-collect/results.md` from this run.
- The project's existing changelog file (CHANGELOG.md, CHANGES.md, or similar).
- `releases/insights.md` (if it exists): learned style preferences.

## Output

Write `2-changelog/results.md` in the run folder with the draft changelog entry.

## How to execute

1. **Find the existing changelog.** Look for CHANGELOG.md, CHANGES.md, HISTORY.md, or similar at the repo root. If none exists, note that a new one will be created.
2. **Read the style.** If a changelog exists, study the most recent 2-3 entries: heading format (## vs ###), grouping (by type, by scope, flat), bullet style, level of detail (commit-level or summary-level), tone (technical, casual, user-facing). If `releases/insights.md` has style notes, use those as a starting point.
3. **Draft the entry.** Group changes from the collect step by type (features, fixes, breaking changes, other). Use the detected style. If no style was detected, use this default:
   - Heading: `## [version] - YYYY-MM-DD`
   - Sections: `### Added`, `### Fixed`, `### Changed`, `### Breaking`
   - One bullet per change, written for the end user (not the developer).
   - Skip chore/refactor/docs unless they affect the user.
4. **Present the draft.** Show the changelog entry to the user. Ask if it looks right. Revise if requested.
5. **Update style insights.** After the user approves (or edits), note any style preferences in `releases/insights.md` for future runs.

## Done when

The user approves the changelog draft. The draft is saved in the run folder.
