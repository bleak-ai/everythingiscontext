# Step 2: Propose the recipe

## Purpose

Turn the exploration into a Python script with parameters. Define what is variable (changes per run) and what is fixed (same every time).

## Input

- The exploration log from step 1: action sequence, selectors, expected states.

## Output

`runs/{slug}/2-recipe.md` with:

- **Recipe name**: kebab-case identifier (e.g. `export-monthly-report`).
- **Parameters**: for each, the name, type, and description.
- **Script**: the full Python source that uses the browser connection to execute the action.
- **Test plan**: how to verify the script works (input values, expected result).

## How to execute

1. Review the exploration log. Identify which values should be parameters (URLs, dates, form values, file paths) and which are fixed navigation steps.
2. Write a Python script that uses the browser connection to execute the action. The script accepts parameters as arguments.
3. Include waits and assertions from the exploration (e.g. wait for an element before clicking, verify a confirmation message).
4. Present the recipe to the user for review.
5. Make adjustments based on feedback.

## Done when

The user has approved the recipe: the script, parameters, and test plan.
