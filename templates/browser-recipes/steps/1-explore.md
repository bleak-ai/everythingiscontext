# Step 1: Explore with the browser

## Purpose

Navigate the target site or app with the browser connection. Find the path from start to goal. Record every step: what to click, what to wait for, what to fill in.

## Input

- The analysis from step 0: target, goal, success definition.
- The browser connection.

## Output

`runs/{slug}/1-exploration.md` with:

- **Action sequence**: a numbered list of every action performed.
- **Selectors**: the CSS selector or element identifier for each action.
- **Expected state**: what the page should look like after each action.
- **Branching**: any conditional paths (e.g. "if a modal appears, close it first").

## How to execute

1. Open the target URL in the browser.
2. Navigate step by step toward the goal. At each step, record the action, the selector, and the result.
3. If you hit a blocker (login required, captcha, unexpected state), document it and ask the user for help.
4. When the goal is achieved, verify the result against the success definition from step 0.
5. Write the exploration log.

## Done when

The goal is achieved and the full action sequence is recorded in the exploration file.
