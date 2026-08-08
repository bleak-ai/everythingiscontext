# Playbook: redeploy an application

Written from a real run. Improve this file after every run that uses it.

## Steps

1. Get the application uuid from `overview.md` (sync first, step 1 of the
   loop). Confirm the app name and uuid with the user before the call.
2. Trigger the deploy. It is a GET request, not a POST, even though it is
   a write operation: `GET /deploy?uuid=<app_uuid>`. Ask the user before
   this call; it is a write operation against the instance.
3. The response contains `deployment_uuid`. Keep it; all follow-up goes
   through it.
4. Poll `GET /deployments/<deployment_uuid>` until `status` is `finished`
   or `failed`; every 15 to 30 seconds is enough, and report to the user
   instead of polling on past 10 minutes. The `logs` field is a
   JSON-encoded string; parse it and read the `output` field of each
   entry.
5. Verify: `GET /applications/<app_uuid>` for status, then an HTTP GET on
   the app's domain. Expect 200.

## Known behavior

- The deploy trigger is a GET endpoint. Every other write API is usually
  POST; do not let the verb fool you, it queues a real deployment.
- A deploy with an unchanged git commit SHA finishes in seconds: Coolify
  skips the build and reuses the image; only the rolling update runs. A
  deploy with a new commit takes minutes, not seconds.
- The logs contain a scary-looking line early on: `Error response from
  daemon: No such container: <deployment_uuid>`. It is harmless; the
  helper checks for a leftover container before creating it.
- The rolling update can warn about an orphan container from the previous
  deployment. Also harmless; Coolify removes the old container itself
  right after.
- App status can stay `running:unknown` even after a successful deploy;
  the `unknown` part is the health check, not a problem by itself. Verify
  with an HTTP request to the domain instead.
