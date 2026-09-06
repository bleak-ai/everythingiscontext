# share-agent

Instructions for an AI that turns a private, lived agent into a distributable template. You are the AI; the human in the conversation is the author. The input is their agent module, personal state included. The output is a template folder that follows the agent template standard ([agents.md](agents.md)) and contains zero personal data.

Work through the phases in order. Propose, let the author confirm, then act. Do not skip a phase.

## Phase 0: load

1. Ask the author which agent module to share, if not already stated. Read it completely: `index.md`, `steps/`, `functions/` and `commands/` if present, and the run folders in `runs/`.
2. Read the template spec ([agents.md](agents.md)). Do not work from memory of the spec; the spec is the contract the output must pass.

## Phase 1: eligibility

Check the agent against the five tests for shareable agents and report the result per test:

1. **Procedure generic, state personal.** The steps contain a loop that is not tied to the author's life; the personal content sits in state files that can start empty for someone else.
2. **The AI is needed every run.** Each run requires interpretation and judgment. If a cron job or a static script could do it, it is not an agent.
3. **The state feeds judgment.** Later runs read the accumulated state to act better. Knowledge qualifies; telemetry nobody consults does not.
4. **Lived first.** At least one real, completed run exists in `runs/`. The shapes must have been discovered by use, not designed on paper.
5. **Low trust barrier.** Few parameter slots, few secrets. Every credential a stranger must grant raises the install cost.

If any test fails, tell the author which and why, and continue only after their explicit confirmation. The registry is open; you warn, the author decides.

## Phase 2: extract the slots

Walk `index.md`, every file in `steps/`, and `functions/` if present. Collect every author-specific element: personal and company names, domains, URLs, account identifiers, email addresses, concrete product names, file paths outside the module, and data values from the author's own work.

Classify each element as exactly one of:

- **(a) Parameter slot**: a value that changes the scope or input of a single run. The test: "does this value appear in `0-parameters.*` and does it change what the run does?" If yes, it is a parameter. If the value configures which service to talk to, which queue to pull from, or how to authenticate, it belongs in the connection, not here. Becomes a `parameters` entry in the manifest.
- **(b) Connection requirement**: a service capability the agent needs, including all configuration that identifies which instance or account to use (team, project, queue, environment). Becomes a structured `connections` entry (`kind` + `description`, plus optional `examples`), described generically ("the hosting panel API", not "Coolify").
- **(c) Personal state**: files or content that must not ship (playbooks learned from the author's systems, configs, credentials references, logs). Excluded from the template; the setup command will regenerate the empty shapes.
- **(d) Generic rewrite**: a concrete-service mention inside a step that stays in the text but must be reworded to the capability kind.

Present the full classification as one list and get the author's confirmation before rewriting anything. This is the author's main control point; the leak scan in phase 5 is the second net.

## Phase 3: generate the template

Create the template folder next to the source module (for example `<agent-id>-template/`). Build:

- **`index.md`**: the frontmatter manifest per the spec: `id` (url-safe slug), `name`, `description`, `parameters` (name, description, required), `connections` (kind, description, optional examples), optional `learns`, `tags`. Then the body, rewritten clean: the objective in the first paragraph, what each parameter means in practice, the agent's run naming scheme, and the general cross-step context.
- **`steps/`**: the same files as the source, with the classified specifics replaced by parameter references and generic capability wording. Keep the structure untouched: the shapes were proven by use; you strip, you do not redesign. Every step file must state Purpose, Input, Output (with schema when tabular), How to execute, and Done when; if a source step lacks one of these, derive it from what the lived runs show and confirm with the author.
- **`functions/`**: same treatment, only if the source has it.
- **`commands/setup.md`**: generate it from the slots, following the setup contract in [agents.md](agents.md): read index.md and steps/index.md first; bind every setup-time parameter; map each connection requirement to a real service in the user's environment; generate the personal state (list in the command exactly what it creates); smoke-test the critical path; never edit steps/. Give it command frontmatter (`description`, optional `parameters`) and a self-contained prose body that assumes only file access.
- **`commands/run.md`**: generate the run driver, following the run command contract in [agents.md](agents.md). It must: read the agent's index.md and steps/index.md, collect per-run parameters, create the run folder with index.md and 0-parameters.*, execute each step in order writing output into per-step folders (e.g. `1-collect/results.md`), update the run's index.md after each step, and close the run with `done/info.md`. Give it command frontmatter (`description`, optional `parameters`) and a self-contained prose body.

## Phase 4: fabricate the example run

Build `runs/example/` inside the template, in the exact runs/ shape: `index.md` (map and status), `0-parameters.*`, one folder per step with results, `done/info.md`.

- Default: start from the author's most representative real run and replace every real value with a coherent fake: invented names, plausible numbers, same schemas, same story arc.
- Fallback: if the author's runs are too sensitive to anonymize confidently, fabricate the example fully from the step definitions. Say so to the author.
- Keep the fake data internally consistent: the same invented name must flow through all steps, so a site visitor can follow one item from parameters to done.

## Phase 5: verify

Run three checks and show the results:

1. **Spec compliance**: every required file exists (index.md with parseable frontmatter carrying all fields, steps/ with index and numbered files, commands/setup.md, commands/run.md, runs/example/ complete with per-step folders and done/); every step states Purpose, Input, Output, How, Done when.
2. **Leak scan**: search the entire template, example run included, for every author-specific string collected in phase 2, plus generic patterns: email addresses, things shaped like API keys or tokens, the author's domains. Present every hit. The template passes only with zero unexplained hits.
3. **Cold read**: in a fresh context that sees only the template folder, have it explain back what the installed agent does, what it needs, and what a run produces. If the explanation is wrong or incomplete, the template is not self-contained; fix and repeat.

## Phase 6: hand off

The finished template is a local folder. Validate it against the template standard. Then submit it by opening a pull request against [github.com/bleak-ai/agents](https://github.com/bleak-ai/agents), adding the folder at the repo root.

Never submit without the author's explicit go-ahead, and never include the source module or any personal state in what is submitted.

A maintainer reviews and merges the pull request. The directory on gcontext.ai renders from the registry.
