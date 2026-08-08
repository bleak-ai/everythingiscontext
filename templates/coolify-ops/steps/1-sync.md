# Step 1: sync the mirror

## Purpose

Keep the mirror (`overview.md`) matching the real state of the Coolify
instance, so every operation starts from trusted facts and drift is
noticed before it surprises anyone. This step runs first on every run,
never optional.

## Input

- The saved sync script at `scripts/sync.py`, generated at setup. It
  takes the instance URL as a command line argument (defaulting to the
  bound value) and reads the API token from the `COOLIFY_API_KEY`
  environment variable. If the script or `overview.md` is missing, setup
  was never run: stop and run `commands/setup.md` first (it contains the
  full script specification).
- The current `overview.md` in the workflow folder, the last trusted state.

## Output

`1-sync/results.md` in the run folder: the drift found, one line per
changed resource, or "no drift" when the mirror already matched. Update
`overview.md` itself so it matches what the API returned.

The mirror format, one line per resource:

```
kind | name | uuid | status | domain
```

Sections: servers, projects, applications, services, databases.

## How to execute

1. Run the saved sync script. It calls, read-only, the Coolify API
   endpoints `/servers`, `/projects`, `/applications`, `/services`,
   `/databases` under `<instance-url>/api/v1` with the bearer token, and
   prints one line per resource in the mirror format.
2. Diff the output against `overview.md`.
3. Update `overview.md` so it matches the API output. Keep the "Last
   sync" date at the top current.
4. Write the drift summary to `1-sync/results.md` in the run folder and
   tell the user what changed since the last sync.

Known Coolify API facts:

- The servers and projects endpoints return no status field; the mirror
  shows `?` there.
- An application status of `running:unknown` means the health check is
  unknown, not that the app is broken. Verify with an HTTP request to the
  app's domain when it matters.

## Done when

`overview.md` matches the live API state, the drift is recorded in
`1-sync/results.md`, and the user has been told what changed.
