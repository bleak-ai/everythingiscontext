# Run closed: 2026-08-02-redeploy-website

## Achieved

Redeployed `acme-website` after a content update. Deployment
`d4g8s2w6e0r4t8y2u6i0o4p8` finished; the site serves the new build and
answers 200 on `https://acme-website.example.com`.

## Learned

- A new-commit deploy took about 4 minutes (build plus rolling update);
  only same-SHA deploys finish in seconds. Added the timing note to the
  playbook.
- The `staging-portal` application drifted to `exited:unhealthy` since
  the last sync. Not this run's scope; the user opened a separate
  investigation for it.

## Playbook effect

`playbooks/redeploy-app.md` improved: added the new-commit timing
expectation next to the same-SHA note.
