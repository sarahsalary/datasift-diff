# Changelog

## [0.8.0] - 2025-07-01

### Added
- **Database sources** for `sqlite://`, `postgres://`, `mysql://`, `mssql://`.
- **Anomaly detection** for numeric changes.
- `datasift-diff-anomaly` CLI.
- Main CLI flags: `--anomaly-history`, `--anomaly-threshold`,
  `--anomaly-method`, `--anomaly-min-history`, `--anomaly-update`,
  `--fail-on-anomaly`.
- `[anomaly]` extra with numpy (optional; pure-Python fallback works).

### Changed
- `io._resolve_source()` handles database URIs.
- `uri.is_db_uri()` and `uri.uri_extension()` recognize database schemes.
- `pyproject.toml` adds `db` and `anomaly` extras.

## [0.7.0] - 2025-06-01

### Added
- **Remote streaming** for S3 and GCS via HTTP Range requests.
- **Git revision support** (`HEAD:data.csv`, `main:users.parquet`).
- **Schema files** in YAML, TOML, and JSON.
- **Web UI** via FastAPI.
- `[web]` extra with fastapi, uvicorn, python-multipart.

### Changed
- `io.load_data()` now handles git specs and remote URIs uniformly.
- `io.stream_records()` dispatches to `stream_uri` for remote sources.

## [0.1.0] - 2025-05-01

### Added
- Initial release.
- CSV, JSON, JSONL support.
- Multi-key comparison.
- Numeric tolerance.
- Nested keys.
- Flatten nested dicts.
- Text, JSON, CSV output.
- Plugin system.