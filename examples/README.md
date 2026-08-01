# Examples

Complete agent folders you can serve directly or copy pieces from. `gcontext init` scaffolds a minimal folder; these show what a grown one looks like.

## ops-agent

An operations agent for a fictional SaaS company. It shows every part of the folder model in use:

- `connections/stripe/`, `connections/cloudflare/`: connection config plus API context docs
- `modules/company/`: a knowledge module (team, infrastructure)
- `modules/support-workflow/`: a process module with steps, empty playbooks and logs that fill up with use
- `archive/modules/legacy-audit/`: an archived module, out of every scan but still readable by path

Run it:

```bash
cp examples/ops-agent/secrets.env.example examples/ops-agent/secrets.env  # fill in real values, or leave placeholders
gcontext up examples/ops-agent
```

Without real secret values everything still works except `run_script` calls against the live APIs; `gcontext status` shows which secrets are missing.
