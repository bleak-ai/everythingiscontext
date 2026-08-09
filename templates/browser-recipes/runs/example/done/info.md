# Done: export-monthly-report

## What was achieved

Recipe "export-monthly-report" created and saved to recipes/. The script navigates app.acme.com, selects the target month, and downloads the sales report. Tested with month=2026-06, format=csv.

## What was learned

The export button only appears after the report finishes loading. The script waits for the `.report-ready` indicator before clicking export. This wait is baked into the recipe.
