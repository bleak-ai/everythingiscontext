---
description: Run an existing recipe by name. Falls back to full exploration if the script fails.
parameters:
  - name: recipe
    description: The recipe name to execute (e.g. "export-monthly-report")
    required: true
---

# Run Recipe

Run a saved recipe from the library. If the recipe fails, fall back to the full exploration workflow and update the recipe.

1. Read `recipes/index.md` to find the recipe named `$recipe`.
2. If the recipe is not found, report the error and list available recipes. Stop.
3. Read `recipes/$recipe.md` to get the recipe metadata: parameters, description, and script path.
4. Ask the user for any required parameter values not already provided.
5. Run the script `recipes/$recipe.py` with the provided parameters.
6. If the script succeeds: report the result. Done.
7. If the script fails: report the error. Fall back to the full workflow (steps 0 through 3) using the original action description from the recipe metadata. The re-exploration will produce an updated recipe that replaces the broken one.
