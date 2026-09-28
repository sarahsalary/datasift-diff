# datasift-diff

Compare two datasets by key — files, remote URIs, git revisions, or databases.

## Installation

```bash
pip install datasift-diff

# With all optional features
pip install datasift-diff[all]
```

## Quick Start

```bash
# Compare two local files
datasift-diff old.csv new.csv --key id

# Multi-key
datasift-diff old.csv new.csv --key user_id,date

# Git revisions
datasift-diff HEAD~1:data.csv HEAD:data.csv --key id

# Remote sources (S3/GCS)
datasift-diff s3://bucket/a.jsonl s3://bucket/b.jsonl --key id

# Databases
datasift-diff 'postgres://user:pass@host/db?table=users' \
              'postgres://user:pass@host/db?table=users_old' --key id

# HTML report
datasift-diff old.csv new.csv --key id --format html -o report.html

# Validate against a schema
datasift-diff old.csv new.csv --key id --validate --schema-file schema.yaml

# Anomaly detection
datasift-diff old.csv new.csv --key id \
    --anomaly-history history.json \
    --anomaly-threshold 3.5 \
    --fail-on-anomaly
```

## Features

- **Formats**: CSV, JSON, JSONL, YAML, TOML, XML, Excel, Parquet
- **Multi-key**: Compare by several fields
- **Nested keys**: `user.id`, `address.city`
- **Numeric tolerance**: `1.0000001` == `1.0000002`
- **Flatten**: Flatten nested dicts before comparison
- **Streaming**: Single-pass merge-join for sorted inputs
- **Remote streaming**: S3/GCS via HTTP Range requests
- **Git revisions**: `HEAD:data.csv`
- **Schema files**: YAML/TOML/JSON
- **Web UI**: `datasift-diff-serve`
- **TUI**: `datasift-diff-tui`
- **Databases**: SQLite, PostgreSQL, MySQL, MSSQL
- **Anomaly detection**: Z-score / IQR
- **Watch mode**: Re-run diff on file changes
- **Plugin system**: Add your own formats and sources

## Python API

```python
from datasift_diff import diff

result = diff("old.csv", "new.csv", key="id")
print(result.summary)
```

## Docs

- [Remote Streaming (S3/GCS)](docs/remote-streaming.md)
- [Git Revisions](docs/git.md)
- [Database Support](docs/database.md)
- [Anomaly Detection](docs/anomaly.md)
- [Web UI](docs/web-ui.md)

## License

MIT