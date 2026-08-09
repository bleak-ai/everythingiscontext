# Step 3: Log

## Purpose

Write the complete run folder with all structured files so the resolution is permanently searchable.

## Input

- The outputs from steps 0-2: intake, plan, execution log.

## Output

The run folder `runs/{ticket-id}-{slug}/` with:

- `index.md`: run summary with ticket ID, category, one-line outcome, and status of each step.
- `1-intake.md`: from step 0 (already written).
- `2-plan.md`: from step 1 (already written).
- `3-execution-log.md`: from step 2 (already written).
- `4-outcome.md`: final state of the ticket and what changed in the product.

## How to execute

1. Write `4-outcome.md` with:
   - **Outcome**: what was resolved, in one sentence.
   - **Changes made**: a summary of every write operation from the execution log.
   - **Human steps**: any manual actions performed outside the agent (or "None").
   - **Verification**: how the fix was confirmed.
2. Write `index.md` for the run folder: ticket ID, category, date, one-line outcome, and a per-step status table (all steps should show "done" or "skipped").
3. No human approval needed for this step; it only writes to the workflow's own files.

## Done when

The run folder has all five files (index, intake, plan, execution-log, outcome) and the index shows all steps complete.
