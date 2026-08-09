# Analysis: export-monthly-report

- **Target**: https://app.acme.com/dashboard
- **Goal**: Download the monthly sales report as a CSV file.
- **Success definition**: A file named `sales-{month}.csv` is downloaded to the local filesystem.
- **Complexity**: Multi-step (login, navigate to reports, select month, click export).

## Notes

The dashboard requires authentication. The user must be logged in before the export action can start. The report page loads data asynchronously, so the export button only appears after the data finishes loading.
