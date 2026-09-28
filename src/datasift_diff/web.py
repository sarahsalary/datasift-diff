"""FastAPI-based web UI for datasift-diff."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from datasift_diff.core import DiffError, diff
from datasift_diff.html_report import render_html
from datasift_diff.io import DataLoadError
from datasift_diff.schema_loader import SchemaLoadError
from datasift_diff.validation import ValidationError, validate_before_diff


def create_app() -> FastAPI:
    app = FastAPI(
        title="datasift-diff",
        description="Web UI for datasift-diff",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _INDEX_HTML

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/diff")
    async def api_diff(
        old: UploadFile = File(...),
        new: UploadFile = File(...),
        key: str = Form(...),
        ignore: str = Form(""),
        tolerance: float | None = Form(None),
        flatten: bool = Form(False),
        schema_file: UploadFile | None = File(None),
    ) -> JSONResponse:
        try:
            old_bytes = await old.read()
            new_bytes = await new.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Upload failed: {e}")

        old_path = _save_temp(old.filename or "old.csv", old_bytes)
        new_path = _save_temp(new.filename or "new.csv", new_bytes)

        try:
            keys = [k.strip() for k in key.split(",") if k.strip()]
            ignore_fields = [f.strip() for f in ignore.split(",") if f.strip()]

            if schema_file is not None:
                schema_bytes = await schema_file.read()
                schema_path = _save_temp(
                    schema_file.filename or "schema.yaml", schema_bytes
                )
                from datasift_diff.io import load_records

                old_records = load_records(str(old_path))
                new_records = load_records(str(new_path))
                validate_before_diff(
                    old_records, new_records, schema_file=str(schema_path)
                )

            result = diff(
                str(old_path),
                str(new_path),
                key=keys,
                ignore_fields=ignore_fields,
                tolerance=tolerance,
                flatten=flatten,
            )
        except (DataLoadError, DiffError, SchemaLoadError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=str(e))
        finally:
            _safe_unlink(old_path)
            _safe_unlink(new_path)

        return JSONResponse(result.to_dict())

    @app.post("/api/report", response_class=HTMLResponse)
    async def api_report(
        old: UploadFile = File(...),
        new: UploadFile = File(...),
        key: str = Form(...),
        ignore: str = Form(""),
        tolerance: float | None = Form(None),
        flatten: bool = Form(False),
    ) -> str:
        try:
            old_bytes = await old.read()
            new_bytes = await new.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Upload failed: {e}")

        old_path = _save_temp(old.filename or "old.csv", old_bytes)
        new_path = _save_temp(new.filename or "new.csv", new_bytes)

        try:
            keys = [k.strip() for k in key.split(",") if k.strip()]
            ignore_fields = [f.strip() for f in ignore.split(",") if f.strip()]
            result = diff(
                str(old_path),
                str(new_path),
                key=keys,
                ignore_fields=ignore_fields,
                tolerance=tolerance,
                flatten=flatten,
            )
        except (DataLoadError, DiffError) as e:
            raise HTTPException(status_code=422, detail=str(e))
        finally:
            _safe_unlink(old_path)
            _safe_unlink(new_path)

        return render_html(result)

    return app


def _save_temp(filename: str, data: bytes) -> Path:
    suffix = Path(filename).suffix or ".dat"
    fd, path_str = tempfile.mkstemp(suffix=suffix)
    path = Path(path_str)
    with open(fd, "wb") as f:
        f.write(data)
    return path


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>datasift-diff — Web UI</title>
<style>
:root {
  --bg: #0d1117; --fg: #c9d1d9; --muted: #8b949e;
  --border: #30363d; --card: #161b22; --accent: #58a6ff;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.5;
}
header {
  padding: 24px; border-bottom: 1px solid var(--border); background: var(--card);
}
h1 { margin: 0; font-size: 22px; }
.subtitle { color: var(--muted); font-size: 13px; margin-top: 4px; }
main { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 24px; margin-bottom: 20px;
}
label { display: block; font-weight: 600; margin-bottom: 6px; font-size: 13px; }
input[type="text"], input[type="number"], input[type="file"], select {
  width: 100%; padding: 8px 12px; background: var(--bg); color: var(--fg);
  border: 1px solid var(--border); border-radius: 6px; font-size: 14px;
  margin-bottom: 16px;
}
input:focus, select:focus {
  outline: none; border-color: var(--accent);
}
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 640px) { .row { grid-template-columns: 1fr; } }
button {
  padding: 10px 20px; background: var(--accent); color: #fff;
  border: none; border-radius: 6px; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: opacity 0.15s;
}
button:hover { opacity: 0.9; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.checkbox-row { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.checkbox-row input { margin: 0; width: auto; }
.checkbox-row label { margin: 0; }
#status {
  padding: 12px; border-radius: 6px; margin-bottom: 16px;
  font-size: 13px; display: none;
}
#status.error { background: rgba(248, 81, 73, 0.1); color: #f85149; border: 1px solid #f85149; }
#status.loading { background: rgba(88, 166, 255, 0.1); color: var(--accent); border: 1px solid var(--accent); }
#result { margin-top: 20px; }
iframe { width: 100%; height: 700px; border: 1px solid var(--border); border-radius: 8px; background: #fff; }
</style>
</head>
<body>
<header>
  <h1>datasift-diff</h1>
  <div class="subtitle">Compare two datasets by key — interactively in your browser.</div>
</header>
<main>
  <form id="diff-form" class="card">
    <div class="row">
      <div>
        <label for="old">Old dataset</label>
        <input type="file" id="old" name="old" required>
      </div>
      <div>
        <label for="new">New dataset</label>
        <input type="file" id="new" name="new" required>
      </div>
    </div>

    <label for="key">Key field(s) — comma-separated for multi-key</label>
    <input type="text" id="key" name="key" placeholder="user_id,date" required>

    <label for="ignore">Ignore fields — comma-separated (optional)</label>
    <input type="text" id="ignore" name="ignore" placeholder="updated_at,hash">

    <div class="row">
      <div>
        <label for="tolerance">Numeric tolerance (optional)</label>
        <input type="number" id="tolerance" name="tolerance" step="any" placeholder="1e-6">
      </div>
      <div>
        <label for="schema">Schema file (optional, requires datasift-py)</label>
        <input type="file" id="schema" name="schema">
      </div>
    </div>

    <div class="checkbox-row">
      <input type="checkbox" id="flatten" name="flatten">
      <label for="flatten">Flatten nested dicts before comparison</label>
    </div>

    <button type="submit" id="submit-btn">Compare</button>
  </form>

  <div id="status"></div>
  <div id="result"></div>
</main>
<script>
const form = document.getElementById('diff-form');
const status = document.getElementById('status');
const result = document.getElementById('result');
const submitBtn = document.getElementById('submit-btn');

function setStatus(kind, msg) {
  status.className = kind;
  status.textContent = msg;
  status.style.display = msg ? 'block' : 'none';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  result.innerHTML = '';
  setStatus('loading', 'Comparing...');
  submitBtn.disabled = true;

  const fd = new FormData();
  fd.append('old', document.getElementById('old').files[0]);
  fd.append('new', document.getElementById('new').files[0]);
  fd.append('key', document.getElementById('key').value);
  fd.append('ignore', document.getElementById('ignore').value);
  const tol = document.getElementById('tolerance').value;
  if (tol) fd.append('tolerance', tol);
  if (document.getElementById('flatten').checked) fd.append('flatten', 'true');
  const schemaFile = document.getElementById('schema').files[0];
  if (schemaFile) fd.append('schema_file', schemaFile);

  try {
    const resp = await fetch('/api/report', { method: 'POST', body: fd });
    if (!resp.ok) {
      const text = await resp.text();
      let detail = text;
      try { detail = JSON.parse(text).detail; } catch (e) {}
      throw new Error(detail || resp.statusText);
    }
    const html = await resp.text();
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    result.innerHTML = '<iframe src="' + url + '"></iframe>';
    setStatus('', '');
  } catch (err) {
    setStatus('error', 'Error: ' + err.message);
  } finally {
    submitBtn.disabled = false;
  }
});
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="datasift-diff-serve",
        description="Run the datasift-diff web UI.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print(
            "error: Web UI requires fastapi and uvicorn. "
            "Install with: pip install datasift-diff[web]",
            file=__import__("sys").stderr,
        )
        return 2

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
