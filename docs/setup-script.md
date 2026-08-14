# The setup script standard

This document defines every text a user reads during install and setup: the CLI banners (`init`, `add`, `up`, `status`), the built-in prompts (setup, and later explain), and the agent-authored files (`commands/setup.md`, example content). Three rules drive it: the framework owns the voice and agents supply data, never dialogue; status reports come from code and appear verbatim; every surface ends with one next-step line in one standard form.

## The setup script

Every setup conversation follows six blocks, in order. The model outputs only the defined blocks' content. No free sentences between blocks.

### Block 1: the report

Code-printed, shown verbatim. The model never rewrites it.

```
Welcome to gcontext
Agent: browser-recipes

Connections
  chrome-cdp     MISSING

Status: needs setup
```

One line per declared connection, status `OK` or `MISSING`. An agent never set up shows `Status: needs setup`. An agent with a lost connection shows `Status: connection missing`. When everything is satisfied: `Status: ready`. The wording of these reports (headings, labels, status words) lives in `gcontext/report_strings.py`, the single source of truth; the report tests import those constants, and the examples in this document illustrate the current values.

### Block 2: the plan

Heading `## Plan`. One plain line per item the setup will create ("chrome-cdp: so the agent can drive your browser"). Items the user already named are approved; only inferred items get a confirmation question.

### Block 3: questions

One question at a time. Standard form: the question, 2-4 options, free answer always possible. Use AskUserQuestion when the runtime has it, plain text otherwise. Never two questions in one message. Never a question the state folder can answer.

### Block 4: build progress

Heading `## Building (2 of 5): <item>`. One line per file written. Smoke test result stated plainly.

### Block 5: examples explained

When the agent ships example content, the script says: "This is a sample. Your own work will appear next to it." Then the agent creates the first real item together with the user.

### Block 6: completion

Heading `## Setup complete`. A short list: what exists now, what was verified. Then the closing line.

## The closing line

Every surface ends with one line that starts with `Next:` and names exactly one action.

```
Next: run /mcp__my-agent__setup to finish the interview.
```

Exception: the `gcontext add` post-install output closes with a `Next steps:` numbered block instead (see the restart rule below). It addresses a human at a terminal, and the restart plus setup sequence is more than one action.

## The restart rule

One wording, reused everywhere a restart is needed in agent-facing text:

"Restart the server (stop, `gcontext up`), then reconnect in your client (`/mcp` in Claude Code)."

The `gcontext add` CLI output uses the numbered form instead:

```
Next steps:
  1. Stop the server (Ctrl-C).
  2. Start it again: gcontext up <dir>
  3. Reconnect in your client: type /mcp in Claude Code.
  4. Run the setup: /mcp__<server>__<module>__setup
```

Step 4 appears only when the installed agent ships `commands/setup.md`. The printed command is the owner-prefixed name ("setup" is a reserved framework stem), copy-pasteable, no backticks.

## Tone rules

- Blocks only. No free sentences between blocks.
- Short sentences. Active voice. Plain words.
- The only gcontext words allowed toward the user are "agent" and "connection". Module, state folder, manifest, frontmatter, and every other internal word gets a plain paraphrase.
- Never ask for secret values. Secret names only.
- Never re-confirm what the user already said.
- No filler ("Great!", "Perfect!"). No apology. No hedging.

## The setup.md contract

`commands/setup.md` is optional. The manifest alone covers agents whose setup is only connections.

When present, setup.md contains only agent-specific steps: extra questions, checks, seed actions. Numbered steps, each with a purpose line. The framework setup prompt runs these steps inside Blocks 3 and 4, after the report and the plan.

setup.md must not contain: a greeting, a report of its own, a completion message, a closing line, or format instructions. The framework script provides all of these.

## CLI banners

All four banners (`init`, `add`, `up`, `status`) share one structure:

1. One title line: `gcontext - <what just happened>`.
2. The facts (what was created or what is running), code-printed, exact.
3. One `Next:` line per the standard form. The add banner points at `/mcp__<server>__setup` and includes the restart rule.

## Connection kinds

`connections` entries in an agent manifest name a capability, not a transport and not a product. The kind values are a fixed enum, checked by the validator:

- `ticket-tracker`
- `product-api`
- `keyword-source`
- `browser`
- `source-control`
- `package-registry`
- `deploy-target`
- `notification-sink`

New kinds enter by editing this list.
