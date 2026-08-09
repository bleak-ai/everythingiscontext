# Step 0: Analyze the action

## Purpose

Understand what the user wants to do. Identify the target site or app, the goal, and define what success looks like after the action completes.

## Input

- `action` parameter: a plain-language description of the browser action.
- `recipes/index.md`: the recipe library, to check for existing matches.

## Output

`runs/{slug}/0-analysis.md` with:

- **Target**: the URL or app to operate on.
- **Goal**: what to achieve, in one sentence.
- **Success definition**: how to verify the action worked (e.g. a file downloaded, a value changed, a confirmation message appeared).
- **Complexity**: single page, multi-step, or requires auth.

## How to execute

1. Parse the action description. Identify the target site, the operation, and the expected result.
2. If the target is unclear, ask the user for the URL or app name.
3. Derive a kebab-case slug from the action description (e.g. "export the monthly report" becomes `export-monthly-report`).
4. Check `recipes/index.md` for an existing recipe that matches this action or a similar one. If a recipe exists, tell the user and suggest the `run-recipe` command instead. Stop here if the user agrees.
5. Write the analysis file. Present it to the user for confirmation.

## Done when

The analysis file is written and the user has confirmed it.
