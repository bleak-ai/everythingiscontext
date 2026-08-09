# 4 - Publish

## Purpose

Tag the release commit, push to the remote, and publish the package to the registry. Skip the registry publish if no registry was configured at setup.

## Input

- The version from step 3.
- The registry connection (if configured).
- The build/publish commands recorded during setup.

## Output

Write `4-publish/results.md` in the run folder with: the tag name, the push result, and the registry publish result (or "skipped").

## How to execute

1. **Create the git tag.** Tag the release commit as `v{version}`. Use an annotated tag with the changelog entry as the message.

2. **Push the commit and tag.** Push the release commit and the tag to the remote:
   ```
   git push origin HEAD
   git push origin v{version}
   ```

3. **Create a release on the git host** (if supported). Use the source-control connection to create a release (e.g. GitHub Release, GitLab Release) with the changelog entry as the body.

4. **Publish to the registry** (skip if not configured).
   - Run the build command recorded during setup (e.g. `uv build`, `npm pack`).
   - Run the publish command (e.g. `uv publish`, `npm publish`).
   - Verify the published version appears on the registry.
   - If publish fails, report the error. Do not roll back the tag (the user decides).

5. **Log the release.** Append a row to `releases/log.md`:
   ```
   | {version} | {date} | {one-line summary} | {notes if any} |
   ```

## Done when

The tag is pushed, the registry publish succeeded (or was skipped), and the release is logged.
