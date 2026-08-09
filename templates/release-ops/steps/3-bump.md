# 3 - Bump

## Purpose

Apply the version bump to the project files. Always confirm with the user before writing.

## Input

- The `version` parameter (if provided by the user).
- `1-collect/results.md`: the change classification (features, fixes, breaking changes).
- The project's version file(s): pyproject.toml, package.json, Cargo.toml, version.go, or similar.

## Output

Write `3-bump/results.md` in the run folder with: the old version, the new version, the reasoning, and the list of files modified.

## How to execute

1. **Determine the new version.**
   - If the user provided an explicit `version` parameter, use it.
   - If not, propose based on the changes:
     - Breaking changes present: major bump.
     - New features, no breaking changes: minor bump.
     - Only fixes and chores: patch bump.
   - Present the proposal to the user with the reasoning. Wait for confirmation.

2. **Find version files.** Scan the repo root for files that contain a version declaration: `pyproject.toml` (version = "..."), `package.json` ("version": "..."), `Cargo.toml`, `setup.cfg`, `version.py`, or any file the setup interview identified. If `scope` is set, look only in the scoped package's directory.

3. **Apply the bump.** Update the version string in every file found. Show the diff to the user before writing.

4. **Update the changelog.** Insert the approved changelog draft (from step 2) into the project's changelog file. Replace the placeholder version heading with the confirmed version number.

5. **Commit.** Stage the changed files and create a commit: `release: v{version}`. Do not push yet (step 4 handles that).

## Done when

The version is bumped in all project files, the changelog is updated, and the release commit is created (not yet pushed).
