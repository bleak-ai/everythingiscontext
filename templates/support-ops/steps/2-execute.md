# Step 2: Execute

## Purpose

Execute the approved plan step by step, with human approval for every write operation.

## Input

- The plan file from step 1: the steps to execute.
- The product connections: to read and write against the product's systems.

## Output

`runs/{ticket-id}-{slug}/3-execution-log.md` with a numbered list of operations performed. Each operation records:

- **Step number**: matches the plan.
- **Service**: which connection was used.
- **Operation**: read or write, and what was done.
- **Details**: the specific identifiers, values, or queries involved.
- **Result**: what happened (success, the value returned, or the error).

## How to execute

For each step in the plan:

1. **Reads**: execute immediately. Record the result.
2. **Writes**: present a confirmation block to the human before executing:
   - **What**: the operation in plain words.
   - **Command**: the specific action or API call.
   - **Impact**: what changes and what is affected.
   Wait for explicit approval. If denied, record "skipped by human" and continue.
3. After execution, verify the result. If the result is unexpected, stop and present the situation to the human before continuing.

Record every operation in the execution log, whether it succeeded or was skipped.

## Done when

All plan steps are executed (or explicitly skipped) and the execution log is written.
