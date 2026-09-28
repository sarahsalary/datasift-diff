"""URI parsing and dispatch for remote sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from datasift_diff.plugins import PluginError, get_registry


class UriError(Exception):
    """Raised when a URI cannot be resolved."""


_DB_SCHEMES = {"postgres", "postgresql", "mysql", "sqlite", "mssql"}


def is_remote_uri(uri: str) -> bool:
    if not isinstance(uri, str):
        return False
    if len(uri) >= 2 and uri[1] == ":":
        if len(uri) >= 3 and uri[2] in ("\\", "/"):
            return False
    parsed = urlparse(uri)
    if not parsed.scheme:
        return False
    if parsed.scheme == "file":
        return False
    return True


def is_db_uri(uri: str) -> bool:
    """Return True if the URI is a database connection string."""
    if not isinstance(uri, str):
        return False
    parsed = urlparse(uri)
    return parsed.scheme.lower() in _DB_SCHEMES


def parse_uri(uri: str) -> tuple[str, str]:
    if is_remote_uri(uri):
        parsed = urlparse(uri)
        return parsed.scheme, uri
    if uri.startswith("file://"):
        return "file", uri[len("file://"):]
    return "file", uri


def parse_db_query_params(uri: str) -> dict[str, Any]:
    """
    Extract diff-related query parameters from a DB URI.

    Supported query params:
        table=<name>        -- table to read
        query=<sql>         -- custom SQL query (URL-encoded)
        columns=a,b,c       -- comma-separated column list
        where=<clause>      -- WHERE clause (URL-encoded)
        order_by=<clause>   -- ORDER BY clause (URL-encoded)
        limit=<n>           -- row limit
        key=<field>         -- convenience: also sets diff key
    """
    parsed = urlparse(uri)
    if not parsed.query:
        return {}

    raw = parse_qs(parsed.query)
    result: dict[str, Any] = {}

    if "table" in raw:
        result["table"] = raw["table"][0]
    if "query" in raw:
        result["query"] = raw["query"][0]
    if "columns" in raw:
        result["columns"] = [c.strip() for c in raw["columns"][0].split(",") if c.strip()]
    if "where" in raw:
        result["where"] = raw["where"][0]
    if "order_by" in raw:
        result["order_by"] = raw["order_by"][0]
    if "limit" in raw:
        try:
            result["limit"] = int(raw["limit"][0])
        except ValueError:
            pass
    if "key" in raw:
        result["key"] = raw["key"][0]
    return result


def fetch_uri(uri: str) -> bytes:
    scheme, body = parse_uri(uri)
    if scheme == "file":
        return Path(body).read_bytes()

    registry = get_registry()
    try:
        source = registry.get_source(scheme)
    except PluginError as e:
        raise UriError(str(e)) from e

    try:
        return source.fetch(uri)
    except Exception as e:
        raise UriError(f"Failed to fetch {uri}: {e}") from e


def stream_uri(uri: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    """
    Stream bytes from a URI.

    For remote sources that support Range requests (S3, GCS), yields chunks
    without downloading the whole object. For file:// and HTTP, falls back
    to a single-chunk yield of the full content.
    """
    scheme, body = parse_uri(uri)

    if scheme == "file":
        with open(body, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        return

    registry = get_registry()
    try:
        source = registry.get_source(scheme)
    except PluginError as e:
        raise UriError(str(e)) from e

    if hasattr(source, "stream_chunks"):
        try:
            yield from source.stream_chunks(uri, chunk_size=chunk_size)
            return
        except Exception as e:
            raise UriError(f"Failed to stream {uri}: {e}") from e

    try:
        yield source.fetch(uri)
    except Exception as e:
        raise UriError(f"Failed to fetch {uri}: {e}") from e


def stream_rows(
    uri: str,
    chunk_size: int = 1000,
    **overrides: Any,
) -> Iterator[dict[str, Any]]:
    """
    Stream rows from a database URI.

    Query parameters are parsed from the URI; `overrides` take precedence.
    """
    if not is_db_uri(uri):
        raise UriError(f"Not a database URI: {uri}")

    params = parse_db_query_params(uri)
    params.update({k: v for k, v in overrides.items() if v is not None})

    scheme = urlparse(uri).scheme.lower()
    registry = get_registry()
    try:
        source = registry.get_source(scheme)
    except PluginError as e:
        raise UriError(str(e)) from e

    if not hasattr(source, "fetch_rows"):
        raise UriError(f"Source for scheme '{scheme}' does not support row streaming.")

    try:
        yield from source.fetch_rows(uri, chunk_size=chunk_size, **params)
    except Exception as e:
        raise UriError(f"Failed to stream rows from {uri}: {e}") from e


def uri_exists(uri: str) -> bool:
    scheme, body = parse_uri(uri)
    if scheme == "file":
        return Path(body).exists()

    registry = get_registry()
    try:
        source = registry.get_source(scheme)
    except PluginError:
        return False
    return source.exists(uri)


def uri_extension(uri: str) -> str:
    if is_db_uri(uri):
        return ".jsonl"

    if "://" in uri:
        parsed = urlparse(uri)
        path = parsed.path
    else:
        path = uri
        if "?" in path:
            path = path.split("?", 1)[0]
        if "#" in path:
            path = path.split("#", 1)[0]
    return Path(path).suffix.lower()