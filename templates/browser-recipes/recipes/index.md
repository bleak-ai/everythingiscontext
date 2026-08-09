# Recipes

Reusable Python scripts for browser actions the agent has performed before. Each recipe has two files: a `.py` file (the executable script) and a `.md` file (metadata, parameters, origin).

The agent consults this index during step 0 (analyze) to find existing recipes. Step 3 (test) adds new entries here after a successful test. When a recipe fails during `run-recipe`, the agent re-explores and updates the recipe automatically.

## Index

_(no recipes yet, they are created as the workflow runs)_
