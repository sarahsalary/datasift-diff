# Web UI

A browser-based interface for `datasift-diff`. Upload two files and get an
interactive HTML report.

## Installation

```bash
pip install datasift-diff[web]
```

## Running

```bash
datasift-diff-serve
# Open http://127.0.0.1:8000
```

Options:

```bash
datasift-diff-serve --host 0.0.0.0 --port 8080
datasift-diff-serve --reload
```

## API Endpoints

### `GET /api/health`

Returns `{"status": "ok"}`.

### `POST /api/diff`

Multipart form with:
- `old` (file)
- `new` (file)
- `key` (string)
- `ignore` (string, optional)
- `tolerance` (float, optional)
- `flatten` (bool, optional)
- `schema_file` (file, optional)

Returns JSON matching `DiffResult.to_dict()`.

### `POST /api/report`

Same inputs as `/api/diff`, returns a self-contained HTML report.

## Deployment

For production, run behind a reverse proxy:

```bash
uvicorn datasift_diff.web:create_app --factory --host 0.0.0.0 --port 8000 --workers 4
```

For Docker:

```dockerfile
FROM python:3.12-slim
RUN pip install datasift-diff[web]
EXPOSE 8000
CMD ["datasift-diff-serve", "--host", "0.0.0.0", "--port", "8000"]
```