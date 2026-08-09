# Exploration: export-monthly-report

## Action sequence

1. **Open the dashboard**: Navigate to `https://app.acme.com/dashboard`.
   - Selector: n/a (direct URL)
   - Expected state: Dashboard home page loads. The sidebar is visible with navigation links.

2. **Click "Reports" in the sidebar**: Navigate to the reports section.
   - Selector: `nav a[href="/reports"]`
   - Expected state: The reports page loads with a list of report categories.

3. **Click "Sales"**: Open the sales reports view.
   - Selector: `a[data-report="sales"]`
   - Expected state: The sales report page loads. A month dropdown and an export button are visible. The export button is disabled until data loads.

4. **Select the target month**: Choose "June 2026" from the month dropdown.
   - Selector: `select#report-month`
   - Value: `2026-06`
   - Expected state: The report data reloads for the selected month. A loading spinner appears, then the `.report-ready` indicator becomes visible.

5. **Wait for the report to finish loading**: The export button enables only after loading completes.
   - Selector: `.report-ready` (wait for this element to appear)
   - Expected state: The export button is now enabled (no longer has the `disabled` attribute).

6. **Click "Export CSV"**: Download the report file.
   - Selector: `button.export-csv`
   - Expected state: A file download starts. The file name is `sales-2026-06.csv`.

## Branching

- If a "Session expired" modal appears at any point, close it and re-authenticate before continuing.
- If the report data fails to load (error banner appears), refresh the page and retry from step 3.
