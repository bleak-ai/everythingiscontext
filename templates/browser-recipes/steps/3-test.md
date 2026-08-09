# Step 3: Test and save the recipe

## Purpose

Run the proposed script. If it works, save it to the recipe library. If it fails, go back to step 1 and re-explore.

## Input

- The recipe from step 2: script, parameters, test plan.
- The browser connection.

## Output

On success:

- `recipes/{name}.py`: the Python script.
- `recipes/{name}.md`: recipe metadata (name, description, parameters, creation date, source run).
- `recipes/index.md`: updated with the new entry.
- `runs/{slug}/done/info.md`: the run completion record.

On failure:

- The failure documented in the run folder. Go back to step 1 with the failure context.

## How to execute

1. Run the Python script with the test parameters from the test plan.
2. Verify the result against the success definition from step 0.
3. If the script succeeds:
   1. Save the script to `recipes/{name}.py`.
   2. Write `recipes/{name}.md` with the recipe metadata: name, description, parameters (name, type, description for each), creation date, and the source run slug.
   3. Update `recipes/index.md` with a new entry for this recipe.
   4. Write `runs/{slug}/done/info.md` with what was achieved and what was learned.
4. If the script fails:
   1. Document the failure: what went wrong, which step broke, the error message.
   2. Go back to step 1 with the failure context so the re-exploration can address the problem.
   3. The updated exploration will produce a new recipe proposal in step 2.

## Done when

The recipe is saved to `recipes/` and the run is closed, OR the failure is documented and step 1 is re-entered.
