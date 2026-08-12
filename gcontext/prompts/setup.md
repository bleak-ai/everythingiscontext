---
description: Guided setup - describe what the agent should do, and build the state for it
parameters:
  - name: request
    description: What you want, in your words (e.g. "an agent for our support team"). Leave empty to be asked.
    required: false
---
You are running gcontext setup for this agent. Setup is a conversation: the
user describes what they want in their own words, you translate that into
state (connections and modules), and you build and verify it through the
gcontext tools.

The user's request, possibly empty: "$request"

## Ground rules

- The user does not need to know gcontext's concepts. Never ask "do you want
  a connection or a module?". They describe goals; YOU decide what each goal
  needs and explain your plan in one plain line per item.
- Setup is not a one-shot. Say early that nothing has to be decided now:
  the user can start with one or two items and add or change anything later
  by running setup again or simply asking the agent.
- Do not re-confirm what the user already said. When the user explicitly
  named a service or a topic, that item is approved; asking "should I add
  the X connection?" again is noise. The plan confirmation (Step 3) also
  counts as write approval for the files that build those items: announce
  each write in one line, but do not ask again per file.
- Inspect before you ask. Never ask the user something the state folder can
  answer. Start with list_dir(".") and read what you need from there.
- When your runtime has an interactive question tool (AskUserQuestion in
  Claude Code), use it for every choice point in this procedure: fixed
  options render as a picker and the user can still type a free answer.
  Without such a tool, ask in plain text. Open-ended questions ("what should
  this agent do?") stay plain text either way.
- Never ask for secret VALUES. Secret values go into secrets.env, which the
  user edits themselves outside this conversation. You only ever handle secret
  NAMEs. If the user pastes a secret value into the chat, tell them not to,
  and tell them to rotate it if the chat leaves their machine.
- Verify at the end. A connection is done when a smoke test passes, a module
  is done when its index.md reads back correctly, never before.

## Detection pass

Before proposing anything new, check whether the modules already present
are actually operational. List modules/, and for each module read its
index.md frontmatter: a `connections:` list, each entry with kind,
description, and sometimes examples. Compare those against the folders
under connections/: a declared connection is satisfied when an existing
connection's kind and description cover that capability, not just when the
names happen to match.

If every module's declared connections are satisfied, this pass has
nothing to say; move straight to Step 1. If any module has unsatisfied
connections, your FIRST message to the user states, in plain words, which
modules are not yet operational and which capabilities are missing, and
offers to build exactly those first. This report is not skippable: it
comes before any question, including questions from a module's own setup.
Jumping straight into an interview hides the gap and takes away the user's
chance to decline. If the user declines, continue with the normal steps.

When the module ships commands/setup.md, do not improvise the interview
yourself: read the module's commands/setup.md with read_file and follow it
for the module-specific questions, but only AFTER the user has accepted
the offer above. This pass only detects and offers; the module's own setup
does the asking.

## Step 1: Inspect

Call list_dir(".") and list_dir on connections/ and modules/ if they exist
(reuse what the detection pass already listed). Note what is already
there: which connections, which modules, whether agent.md is still the
init placeholder ("Describe what this agent is for..."). This is your map,
not the user's briefing.

## Step 2: Understand what the user wants

If "$request" already describes it, work from that. Otherwise ask, in plain
text and adapted to what you found:

- Fresh instance (nothing there yet): "What should this agent do for you?
  Describe it like you would to a new hire: what it should know, which
  services and tools it should be able to use, what you want to ask of it."
- Instance with existing state: say in one or two lines what the agent
  already has (in plain words, not folder names) and ask what they want to
  add or change. If something looks broken or half-finished (beyond what
  the detection pass already offered), mention it and offer to fix it as
  part of the work.

Let them answer in one messy paragraph. That is the expected input, not a
special case. Ask at most one or two follow-ups if the answer leaves you
unable to plan; do not interrogate.

## Step 3: Propose the plan

Translate the description into a plan. The mapping is yours to make:

- A service the agent must reach (Stripe, Slack, GitHub, an internal API):
  a connection each.
- Knowledge the agent must hold (how the company works, a product, a process,
  a team's rules): a module each. Prefer a few broad modules over many thin
  ones; a module can grow files later.
- If agent.md is still the placeholder, write it yourself from the user's
  description. It is not a plan item and never a question: do not ask what
  it should say or confirm its content, just write it at the start of the
  build and mention in one line that you did.

Show the plan as a short list, one plain line per item ("stripe: so the agent
can look up payments and refunds"). Items the user explicitly asked for are
already approved; confirm only the items you inferred yourself, as a choice
question (multi-select when the tool supports it). If every item was
explicitly requested, skip the confirmation and start building. First-time
setups with many items are the normal case; do not talk the user out of a
big plan, but order it so something useful exists early, and remind them
the rest can always be added later.

## Step 4: Build, one item at a time

Work through the confirmed plan. Finish each item before starting the next,
and say briefly where you are ("2 of 5"). Suggested order: agent.md
first (written directly from the description, no questions), then modules
(they only need conversation), then connections (each needs the user to
place secrets).

**Add a connection:**

1. If anything is unclear, ask what they mainly want to do with the service;
   it shapes the index.md and the smoke test. Decide the auth model and
   secret NAMEs (e.g. SLACK_BOT_TOKEN) and the Python deps (e.g. requests).
   Prefer plain HTTPS via requests over heavy SDKs unless the user wants the
   SDK. When the service has more than one auth model (token vs OAuth app,
   cloud vs self-hosted), present the options as a choice question.
2. If a connection with that name already exists, stop and ask: extend it or
   leave it alone. Never overwrite silently.
3. Write connections/<service>/connection.yaml:

       name: <service>
       description: <one line>
       secrets:
         - <SECRET_NAME>
       deps:
         - <package>

4. Write connections/<service>/index.md: what the service is used for here,
   base URL, auth style (header name, token type), the endpoints that matter
   for the user's stated goal, and known quirks. Write what a fresh session
   needs to use the API, not marketing.
5. Tell the user to add the secret VALUES to secrets.env in the agent folder,
   one NAME=value per line, and to say "done" when they have. When the plan
   has several connections, offer to list all needed NAMEs at once so they
   can fill secrets.env in one sitting.
6. Smoke test with run_adhoc_script: first check the secrets are injected
   (os.environ.get("<SECRET_NAME>") is set; print present/missing, never the
   value), then make one harmless authenticated call (whoami, list, or
   similar). If it fails, read the error, fix connection.yaml or the script,
   and retry. Common causes: missing value in secrets.env (the server reads
   it live, no restart needed), wrong header format, wrong base URL.
7. Once the call works, save it as the first proven script under
   connections/<service>/scripts/ and record in index.md anything the test
   taught you (rate limits, response shapes, error formats).

**Add a module:**

1. From the user's description (plus at most one follow-up), agree on a short
   kebab-case folder name. If the module already exists, extend its index.md
   instead.
2. Write modules/<name>/index.md: what the module covers, what belongs in it,
   and any starting knowledge from this conversation. Seed real content the
   user gave you, not empty headings.
3. If the module will hold an append-only log (decisions, incidents), create
   that file too, with its format stated at the top.
4. Read the index.md back and confirm with the user it says what they meant.

**Health check** (when the user asks for it, or Step 1 found problems):

Work through these, report findings, and offer the fixes as a choice
question (multi-select when the tool supports it):

- Connections without an index.md, or with a connection.yaml that does not
  parse (name missing, bad YAML).
- Declared secret NAMEs that are not set: check via run_adhoc_script with
  os.environ.get(name), print present/missing only.
- Modules without an index.md, or with an index.md that is empty.
- agent.md still the init placeholder: offer to write it from the
  user's description.
- Stale index.md claims: if an index.md documents scripts that do not exist,
  or scripts exist that no index.md mentions, flag the drift.

Fixes go through write_file, run_adhoc_script and run_script like any other work.
Anything that
requires deleting or moving files is out of your reach: name the paths and
tell the user to do it by hand.

## Step 5: Close

Update the relevant index.md files with what this setup added or changed, so
the next session starts smarter. Then summarize for the user in plain words:
what the agent can now do, what was skipped or is still pending (e.g. secrets
never provided), and one example of something they can ask the agent right
now.
