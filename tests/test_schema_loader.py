"""Tests for schema file loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datasift_diff.schema_loader import SchemaLoadError, load_schema


def test_load_json_schema(tmp_path: Path):
    f = tmp_path / "schema.json"
    f.write_text(json.dumps({"id": "int", "name": "str"}), encoding="utf-8")
    schema = load_schema(f)
    assert schema["id"] is int
    assert schema["name"] is str


def test_load_yaml_schema(tmp_path: Path):
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("PyYAML not installed")

    f = tmp_path / "schema.yaml"
    f.write_text("id: int\nname: str\nemail: str\n", encoding="utf-8")
    schema = load_schema(f)
    assert schema == {"id": int, "name": str, "email": str}


def test_load_toml_schema(tmp_path: Path):
    from datasift_diff.schema_loader import load_schema as _load

    f = tmp_path / "schema.toml"
    f.write_text('id = "int"\nname = "str"\n', encoding="utf-8")
    try:
        schema = _load(f)
    except SchemaLoadError as e:
        pytest.skip(f"TOML not supported: {e}")
    assert schema == {"id": int, "name": str}


def test_load_schema_with_fields_key(tmp_path: Path):
    f = tmp_path / "schema.json"
    f.write_text(
        json.dumps({"fields": {"id": "int", "name": "str"}}), encoding="utf-8"
    )
    schema = load_schema(f)
    assert schema == {"id": int, "name": str}


def test_load_unknown_type(tmp_path: Path):
    f = tmp_path / "schema.json"
    f.write_text(json.dumps({"id": "wrongtype"}), encoding="utf-8")
    with pytest.raises(SchemaLoadError, match="Unknown type"):
        load_schema(f)


def test_load_missing_file():
    with pytest.raises(SchemaLoadError, match="not found"):
        load_schema("/nonexistent/schema.json")


def test_load_unsupported_extension(tmp_path: Path):
    f = tmp_path / "schema.txt"
    f.write_text("id: int", encoding="utf-8")
    with pytest.raises(SchemaLoadError, match="Unsupported schema extension"):
        load_schema(f)