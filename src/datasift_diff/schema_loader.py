"""Load schema definitions from YAML, TOML, or JSON files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SchemaLoadError(Exception):
    """Raised when a schema file cannot be loaded."""


_TYPE_MAP = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "number": float,
    "bool": bool,
    "boolean": bool,
    "list": list,
    "array": list,
    "dict": dict,
    "object": dict,
    "any": Any,
    "none": type(None),
    "null": type(None),
}


def _resolve_type(name: str) -> type:
    """Map a type name string to a Python type."""
    key = name.lower().strip()
    if key not in _TYPE_MAP:
        raise SchemaLoadError(
            f"Unknown type '{name}'. Known types: {', '.join(sorted(_TYPE_MAP))}"
        )
    return _TYPE_MAP[key]


def _normalize_schema(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a schema dict, converting type name strings to Python types."""
    if "fields" in raw and isinstance(raw["fields"], dict):
        raw = raw["fields"]

    normalized: dict[str, Any] = {}
    for field, type_spec in raw.items():
        if isinstance(type_spec, str):
            normalized[field] = _resolve_type(type_spec)
        elif isinstance(type_spec, dict):
            normalized[field] = _normalize_schema(type_spec)
        elif isinstance(type_spec, type):
            normalized[field] = type_spec
        elif isinstance(type_spec, list):
            if len(type_spec) == 1 and isinstance(type_spec[0], str):
                normalized[field] = [_resolve_type(type_spec[0])]
            else:
                normalized[field] = type_spec
        else:
            normalized[field] = type_spec
    return normalized


def load_schema(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a schema definition from a file (.json, .yaml, .yml, .toml)."""
    if isinstance(path, os.PathLike):
        path = os.fspath(path)

    ext = Path(path).suffix.lower()

    try:
        raw_bytes = Path(path).read_bytes()
    except FileNotFoundError as e:
        raise SchemaLoadError(f"Schema file not found: {path}") from e

    try:
        if ext == ".json":
            raw = json.loads(raw_bytes.decode("utf-8"))
        elif ext in (".yaml", ".yml"):
            import yaml

            raw = yaml.safe_load(raw_bytes.decode("utf-8"))
        elif ext == ".toml":
            try:
                import tomllib

                raw = tomllib.loads(raw_bytes.decode("utf-8"))
            except ImportError:
                import tomli

                raw = tomli.loads(raw_bytes.decode("utf-8"))
        else:
            raise SchemaLoadError(
                f"Unsupported schema extension '{ext}'. Use .json, .yaml, .yml, or .toml."
            )
    except ImportError as e:
        raise SchemaLoadError(
            f"Missing dependency for {ext} schema. Install the matching extra."
        ) from e
    except Exception as e:
        raise SchemaLoadError(f"Failed to parse schema {path}: {e}") from e

    if not isinstance(raw, dict):
        raise SchemaLoadError(
            f"Schema must be a mapping, got {type(raw).__name__}"
        )

    return _normalize_schema(raw)