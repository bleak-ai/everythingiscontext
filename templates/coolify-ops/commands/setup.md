---
description: Set up the coolify-ops workflow for your Coolify instance (interview, personal state, smoke test)
---

# Setup: coolify-ops

You are the agent running this setup. Interview the user, build their
personal state, and smoke-test the connection. Work through the sections
in order. This file assumes only file access and the ability to make HTTP
requests; it works the same inside gcontext and standalone in any agent.

## 1. Read first

Read the workflow's `index.md` and `steps/index.md` before asking
anything, so the interview is informed. Skim `runs/example/` to see what
a correct run looks like.

## 2. Bind the parameter

Ask for `instance-url`: the base URL of the user's Coolify instance, for
example `https://coolify.example.com`. All API calls go to
`<instance-url>/api/v1`.

## 3. Map the connection

The workflow needs one connection: the Coolify API, authenticated with a
bearer token.

- Ask the user for an API token of the instance (created in the Coolify
  UI under Keys & Tokens, API tokens).
- Store it as a secret named `COOLIFY_API_KEY` in whatever secret
  mechanism the environment has (in gcontext: the instance's secrets;
  standalone: an environment variable or the agent's secret store).
  Never write the token value into any file of this workflow.

## 4. Generate the personal state

Create these files in the workflow folder (they are the user's own state;
the template never ships them):

- `overview.md`: the mirror. Start it empty, with exactly these section
  headings, in this order, and a `Last sync: never` line at the top:
  `## servers`, `## projects`, `## applications`, `## services`,
  `## databases`. Step 1 of the first run fills it.
- `scripts/sync.py`: the sync script. Write it read-only, to this
  specification:
  - Takes the instance URL as a command line argument, defaulting to the
    bound `instance-url` value (bake the bound value into the script as
    the argument default; that is where it is persisted); reads the
    token from the
    `COOLIFY_API_KEY` environment variable and fails with a clear
    message if the variable is unset.
  - Calls `GET /servers`, `/projects`, `/applications`, `/services`,
    `/databases` under `<instance-url>/api/v1` with the header
    `Authorization: Bearer <token>`. Each endpoint returns a bare JSON
    array of resource objects.
  - Prints one line per resource in the mirror format
    `kind | name | uuid | status | domain`, grouped under the five
    section headings. Print `?` when a resource has no status field
    (servers and projects have none) and `-` when it has no domain. For
    applications the domain is the `fqdn` field; services carry domains
    on their inner applications' `fqdn`; databases have none.
  - Standard library only, or a common HTTP library if one is already
    available. No write calls of any kind in this script.

Leave `runs/example/` in place; the user's own runs get their own folders
next to it, named `<date>-<operation-slug>`.

## 5. Smoke test

First verify the secret is retrievable (the `COOLIFY_API_KEY` variable
is set and non-empty). Then run the sync script once (read-only). If it
prints the resource lines, write the first real `overview.md` from its
output and show the user a short summary of their fleet. If it fails:
a 401 means the token is wrong, a DNS error or 404 means the URL or the
`/api/v1` path is wrong. Fix it with the user before declaring setup
done.

## 6. Never edit the procedure

Setup personalizes state only. Do not edit anything in `steps/`,
`playbooks/`, or `runs/example/`.
