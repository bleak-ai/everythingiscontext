# 1 - Collect

## Purpose

Gather all changes since the last release and classify them. This is the raw material for the changelog.

## Input

- The last release tag (from preflight).
- The `scope` parameter (if set, filter to paths owned by the scoped package).
- `releases/insights.md` (if it exists): the repo's detected commit style.

## Output

Write `1-collect/results.md` in the run folder with:

- A list of commits (hash, author, message) since the last tag.
- A classification of each commit: feature, fix, breaking change, chore, docs, refactor, or other.
- A `style` field: "conventional" if more than half the commits follow a conventional-commit format, "freeform" otherwise.
- A summary of contributors.

## How to execute

1. **Get the commit list.** Run `git log --oneline <last-tag>..HEAD`. If `scope` is set, add `-- <scope-path>` to filter.
2. **Detect commit style.** Scan commit messages for conventional-commit prefixes (feat:, fix:, chore:, docs:, refactor:, breaking:, etc.). If more than half match, mark the style as "conventional". Otherwise mark it "freeform".
3. **Classify each commit.** For conventional commits, use the prefix. For freeform commits, read the message and the diff to classify.
4. **Flag breaking changes.** Look for "BREAKING CHANGE" in commit bodies, or "!" after the type prefix (e.g. "feat!:"). Also flag commits that remove public API surface.
5. **Record in `releases/insights.md`.** If the file exists, update the detected style. If it does not exist, note the style for later creation (step 2 will create the file after the first run).

## Done when

The results file lists every commit, classified, with a style marker and contributor summary.
