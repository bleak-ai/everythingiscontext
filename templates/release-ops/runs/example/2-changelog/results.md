# Changelog Draft

## [0.3.0] - 2026-07-20

### Added

- Streaming export for large datasets: process millions of rows without loading them all into memory.
- Parquet output format: export directly to `.parquet` files alongside CSV and JSON.
- Progress callback on the export API: track export progress in real time.

### Fixed

- Memory leak in the batch processor when processing more than 100k rows.
- CSV quoting for fields that contain commas or newlines.
