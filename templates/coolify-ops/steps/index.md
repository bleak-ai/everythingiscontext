# Steps

## Starting a run

When the user requests an operation, the agent opens the run before step
1: create `runs/<date>-<operation-slug>/`, write `0-parameters.md` (the
requested operation, its target, who asked, when), and write the run's
`index.md` with a status table listing the three steps, all pending.
Update that table as each step finishes. See `runs/example/index.md` for
the closed-run shape.

## The loop

The loop, executed in order on every run:

1. `1-sync.md`: sync the mirror against the live API, report drift. Always first, never optional.
2. `2-operate.md`: perform the requested operation, playbooks first.
3. `3-close.md`: close the run folder, write or improve the playbook.
