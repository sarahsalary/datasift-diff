"""I/O layer: format plugins + URI sources + git revisions + DB rows."""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, Iterator

from datasift_diff.git import GitError, is_git_spec, read_from_git
from datasift_diff.plugins import PluginError, get_registry
from datasift_diff.uri import (
    UriError,
    fetch_uri,
    is_db_uri,
    is_remote_uri,
    parse_db_query_params,
    stream_rows,
    stream_uri,
    uri_extension,
)


class DataLoadError(Exception):
    """Raised when a data file cannot be loaded."""


class _SourceSpec:
    def __init__(self, fetch_fn, stream_fn, ext: str, description: str) -> None:
        self.fetch_fn = fetch_fn
        self.stream_fn = stream_fn
        self.ext = ext
        self.description = description

    def fetch(self) -> bytes:
        return self.fetch_fn()

    def stream(self, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        return self.stream_fn(chunk_size)

    def read_all(self) -> bytes:
        return b"".join(self.stream())


def _resolve_source(spec: str | os.PathLike[str]) -> _SourceSpec:
    if isinstance(spec, os.PathLike):
        spec = os.fspath(spec)

    # Database URI: emit JSONL (one JSON object per line), not a JSON array.
    if is_db_uri(spec):
        def _fetch() -> bytes:
            lines = []
            for row in stream_rows(spec):
                lines.append(json.dumps(row, default=str, ensure_ascii=False))
            return "\n".join(lines).encode("utf-8")

        def _stream(chunk_size: int) -> Iterator[bytes]:
            buffer: list[str] = []
            buffer_size = 0
            for row in stream_rows(spec):
                line = json.dumps(row, default=str, ensure_ascii=False)
                buffer.append(line)
                buffer_size += len(line) + 1
                if buffer_size >= chunk_size:
                    yield ("\n".join(buffer) + "\n").encode("utf-8")
                    buffer = []
                    buffer_size = 0
            if buffer:
                yield ("\n".join(buffer) + "\n").encode("utf-8")

        return _SourceSpec(
            fetch_fn=_fetch,
            stream_fn=_stream,
            ext=".jsonl",
            description=spec,
        )

    if is_git_spec(spec):
        rev, _, path = spec.partition(":")
        ext = os.path.splitext(path)[1].lower()

        def _fetch() -> bytes:
            return read_from_git(spec)

        def _stream(chunk_size: int) -> Iterator[bytes]:
            data = read_from_git(spec)
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        return _SourceSpec(_fetch, _stream, ext, f"git:{spec}")

    if is_remote_uri(spec):
        ext = uri_extension(spec)

        def _fetch() -> bytes:
            return fetch_uri(spec)

        def _stream(chunk_size: int) -> Iterator[bytes]:
            yield from stream_uri(spec, chunk_size=chunk_size)

        return _SourceSpec(_fetch, _stream, ext, spec)

    ext = os.path.splitext(spec)[1].lower()

    def _fetch() -> bytes:
        try:
            with open(spec, "rb") as f:
                return f.read()
        except FileNotFoundError as e:
            raise DataLoadError(f"File not found: {spec}") from e

    def _stream(chunk_size: int) -> Iterator[bytes]:
        try:
            with open(spec, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except FileNotFoundError as e:
            raise DataLoadError(f"File not found: {spec}") from e

    return _SourceSpec(_fetch, _stream, ext, str(spec))


def _get_format_for_extension(ext: str):
    if not ext:
        raise DataLoadError("Cannot determine format: no file extension found.")
    registry = get_registry()
    plugin = registry.get_format_for_extension(ext)
    if plugin is None:
        available = ", ".join(registry.list_formats()) or "(none)"
        raise DataLoadError(
            f"No format plugin registered for extension '{ext}'. "
            f"Available formats: {available}."
        )
    return plugin


def load_data(spec: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Load records from a file, URI, git revision, or database."""
    source = _resolve_source(spec)
    plugin = _get_format_for_extension(source.ext)
    try:
        data = source.fetch()
        return plugin.load(data)
    except ImportError as e:
        raise DataLoadError(str(e)) from e
    except (UriError, GitError) as e:
        raise DataLoadError(str(e)) from e
    except Exception as e:
        raise DataLoadError(f"Failed to parse {source.description}: {e}") from e


def load_records(
    data: Iterable[dict[str, Any]] | str | os.PathLike[str],
) -> list[dict[str, Any]]:
    if isinstance(data, (str, os.PathLike)):
        return load_data(data)
    return list(data)


def stream_records(
    data: Iterable[dict[str, Any]] | str | os.PathLike[str],
    chunk_size: int = 1024 * 1024,
) -> Iterator[dict[str, Any]]:
    if not isinstance(data, (str, os.PathLike)):
        yield from data
        return

    if isinstance(data, os.PathLike):
        data = os.fspath(data)

    source = _resolve_source(data)
    plugin = _get_format_for_extension(source.ext)

    if hasattr(plugin, "stream"):
        raw = source.read_all()
        yield from plugin.stream(raw)
    else:
        yield from load_data(data)


def iter_chunks(
    spec: str | os.PathLike[str],
    chunk_size: int = 1024 * 1024,
) -> Iterator[bytes]:
    source = _resolve_source(spec)
    yield from source.stream(chunk_size)