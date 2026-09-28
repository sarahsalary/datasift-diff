"""Plugin registry for formats and URI schemes."""

from __future__ import annotations

import csv
import importlib
import io
import json
from typing import Any, Iterator


class PluginError(Exception):
    """Raised when a plugin cannot be resolved."""


# ---------------------------------------------------------------------------
# Format plugins
# ---------------------------------------------------------------------------


class FormatPlugin:
    """Base class for format plugins."""

    name: str = ""
    extensions: list[str] = []

    def load(self, data: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError

    def dump(self, records: list[dict[str, Any]]) -> bytes:
        raise NotImplementedError


class CsvPlugin(FormatPlugin):
    name = "csv"
    extensions = [".csv", ".tsv"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        text = data.decode("utf-8-sig")
        delimiter = "\t" if data.lstrip().startswith(b"\t") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        return [dict(row) for row in reader]

    def dump(self, records: list[dict[str, Any]]) -> bytes:
        if not records:
            return b""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        return buf.getvalue().encode("utf-8")


class JsonPlugin(FormatPlugin):
    name = "json"
    extensions = [".json"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        parsed = json.loads(data.decode("utf-8"))
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        raise PluginError("JSON must be an object or array of objects.")

    def dump(self, records: list[dict[str, Any]]) -> bytes:
        return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


class JsonlPlugin(FormatPlugin):
    name = "jsonl"
    extensions = [".jsonl", ".ndjson"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        records = []
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records

    def stream(self, data: bytes) -> Iterator[dict[str, Any]]:
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)

    def dump(self, records: list[dict[str, Any]]) -> bytes:
        return "\n".join(
            json.dumps(r, ensure_ascii=False) for r in records
        ).encode("utf-8")


class _YamlPlugin(FormatPlugin):
    name = "yaml"
    extensions = [".yaml", ".yml"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        import yaml

        parsed = yaml.safe_load(data.decode("utf-8"))
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        raise PluginError("YAML must be an object or array of objects.")


class _TomlPlugin(FormatPlugin):
    name = "toml"
    extensions = [".toml"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        text = data.decode("utf-8")
        try:
            import tomllib

            parsed = tomllib.loads(text)
        except ImportError:
            import tomli

            parsed = tomli.loads(text)
        if isinstance(parsed, dict):
            return [parsed]
        raise PluginError("TOML must be a table.")


class _XmlPlugin(FormatPlugin):
    name = "xml"
    extensions = [".xml"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        from lxml import etree

        root = etree.fromstring(data)
        records = []
        for child in root:
            records.append({sub.tag: sub.text for sub in child})
        return records


class _ExcelPlugin(FormatPlugin):
    name = "excel"
    extensions = [".xlsx", ".xlsm"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h) for h in rows[0]]
        return [dict(zip(headers, row)) for row in rows[1:]]


class _ParquetPlugin(FormatPlugin):
    name = "parquet"
    extensions = [".parquet"]

    def load(self, data: bytes) -> list[dict[str, Any]]:
        import pyarrow.parquet as pq

        table = pq.read_table(io.BytesIO(data))
        return table.to_pylist()


# ---------------------------------------------------------------------------
# Lazy source wrapper
# ---------------------------------------------------------------------------


class _LazySource:
    """
    A proxy that defers source instantiation until first attribute access.

    This lets us register S3/GCS/DB sources even when the optional
    dependency (boto3, psycopg, ...) is not installed. The ImportError
    is raised only when the source is actually used.
    """

    def __init__(self, scheme: str, module_path: str, class_name: str) -> None:
        self.scheme = scheme
        self._module_path = module_path
        self._class_name = class_name
        self._instance: Any = None

    def _get(self):
        if self._instance is None:
            module = importlib.import_module(self._module_path)
            cls = getattr(module, self._class_name)
            self._instance = cls()
        return self._instance

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


# Built-in sources that are always available (no optional deps).
_ALWAYS_AVAILABLE_SOURCES = (
    ("file", "datasift_diff.sources.file_source", "FileSource"),
    ("http", "datasift_diff.sources.http_source", "HttpSource"),
    ("https", "datasift_diff.sources.http_source", "HttpSource"),
)

# Optional sources: registered lazily. They appear in `--list-schemes`
# even if their deps aren't installed; using them will raise ImportError.
_OPTIONAL_SOURCES = (
    ("s3", "datasift_diff.sources.s3_source", "S3Source"),
    ("gs", "datasift_diff.sources.gcs_source", "GcsSource"),
    ("sqlite", "datasift_diff.sources.db_source", "SqliteSource"),
    ("postgres", "datasift_diff.sources.db_source", "PostgresSource"),
    ("postgresql", "datasift_diff.sources.db_source", "PostgresSource"),
    ("mysql", "datasift_diff.sources.db_source", "MySqlSource"),
    ("mssql", "datasift_diff.sources.db_source", "MssqlSource"),
)


class _Registry:
    def __init__(self) -> None:
        self._formats: dict[str, FormatPlugin] = {}
        self._ext_to_format: dict[str, str] = {}
        self._sources: dict[str, Any] = {}

        # Formats: always-available
        self.register_format(CsvPlugin())
        self.register_format(JsonPlugin())
        self.register_format(JsonlPlugin())

        # Formats: optional (only register if import succeeds)
        for factory in (
            _YamlPlugin,
            _TomlPlugin,
            _XmlPlugin,
            _ExcelPlugin,
            _ParquetPlugin,
        ):
            try:
                plugin = factory()
            except Exception:
                continue
            self.register_format(plugin)

        # Sources: always-available (instantiate immediately)
        for scheme, module_path, class_name in _ALWAYS_AVAILABLE_SOURCES:
            try:
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                source = cls()
                source.scheme = scheme
                self._sources[scheme] = source
            except Exception:
                # Should not happen for file/http, but keep robust.
                continue

        # Sources: optional (lazy)
        for scheme, module_path, class_name in _OPTIONAL_SOURCES:
            self._sources.setdefault(
                scheme, _LazySource(scheme, module_path, class_name)
            )

    # -- formats ---------------------------------------------------------

    def register_format(self, plugin: FormatPlugin, override: bool = False) -> None:
        if plugin.name in self._formats and not override:
            return
        self._formats[plugin.name] = plugin
        for ext in plugin.extensions:
            self._ext_to_format[ext.lower()] = plugin.name

    def get_format(self, name: str) -> FormatPlugin:
        if name not in self._formats:
            raise PluginError(f"No format plugin named '{name}'.")
        return self._formats[name]

    def get_format_for_extension(self, ext: str) -> FormatPlugin | None:
        name = self._ext_to_format.get(ext.lower())
        return self._formats[name] if name else None

    def list_formats(self) -> list[str]:
        return sorted(self._formats)

    # -- sources ---------------------------------------------------------

    def register_source(self, source: Any, override: bool = False) -> None:
        scheme = getattr(source, "scheme", None)
        if not scheme:
            raise PluginError("Source must have a 'scheme' attribute.")
        if scheme in self._sources and not override:
            return
        self._sources[scheme] = source

    def get_source(self, scheme: str) -> Any:
        if scheme not in self._sources:
            raise PluginError(f"No source plugin for scheme '{scheme}'.")
        return self._sources[scheme]

    def list_schemes(self) -> list[str]:
        return sorted(self._sources)


_REGISTRY: _Registry | None = None


def get_registry() -> _Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _Registry()
    return _REGISTRY
