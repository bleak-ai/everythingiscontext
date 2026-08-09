# Recipe proposal: export-monthly-report

## Recipe name

`export-monthly-report`

## Parameters

| Name   | Type   | Description                                      |
|--------|--------|--------------------------------------------------|
| month  | string | The target month in YYYY-MM format (e.g. "2026-06") |
| format | string | Output format: "csv" or "xlsx" (default: "csv")  |

## Script

```python
"""Export the monthly sales report from app.acme.com."""

import argparse


def run(browser, month: str, format: str = "csv"):
    """Navigate the admin dashboard and download the sales report."""

    # 1. Open the dashboard
    browser.goto("https://app.acme.com/dashboard")

    # 2. Click Reports in the sidebar
    browser.click('nav a[href="/reports"]')
    browser.wait_for_selector('a[data-report="sales"]')

    # 3. Click Sales
    browser.click('a[data-report="sales"]')
    browser.wait_for_selector("select#report-month")

    # 4. Select the target month
    browser.select("select#report-month", month)

    # 5. Wait for the report to finish loading
    browser.wait_for_selector(".report-ready", timeout=30000)

    # 6. Click the export button
    export_selector = f"button.export-{format}"
    browser.click(export_selector)

    # 7. Wait for the download to complete
    downloaded = browser.wait_for_download(timeout=15000)
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--format", default="csv", choices=["csv", "xlsx"])
    args = parser.parse_args()
    # browser is injected by the runtime
    run(browser, args.month, args.format)
```

## Test plan

1. Run with `month=2026-06`, `format=csv`.
2. Verify that a file named `sales-2026-06.csv` is downloaded.
3. Check that the file is not empty and contains CSV headers.
