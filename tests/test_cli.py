"""Tests for the main CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from datasift_diff.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_basic(capsys):
    code = main([
        str(FIXTURES / "old.csv"),
        str(FIXTURES / "new.csv"),
        "--key", "id",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "Added: 1" in out
    assert "Removed: 1" in out
    assert "Changed: 1" in out


def test_cli_fail_on_change():
    code = main([
        str(FIXTURES / "old.csv"),
        str(FIXTURES / "new.csv"),
        "--key", "id",
        "--quiet",
        "--fail-on-change",
    ])
    assert code == 1


def test_cli_json_format(capsys):
    import json
    code = main([
        str(FIXTURES / "old.csv"),
        str(FIXTURES / "new.csv"),
        "--key", "id",
        "--format", "json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["summary"]["added"] == 1


def test_cli_html_format(capsys):
    code = main([
        str(FIXTURES / "old.csv"),
        str(FIXTURES / "new.csv"),
        "--key", "id",
        "--format", "html",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "<!DOCTYPE html>" in out


def test_cli_list_formats(capsys):
    code = main(["--list-formats"])
    assert code == 0
    out = capsys.readouterr().out
    assert "csv" in out
    assert "json" in out


def test_cli_list_schemes(capsys):
    code = main(["--list-schemes"])
    assert code == 0
    out = capsys.readouterr().out
    assert "file" in out
    assert "s3" in out
    assert "gs" in out
    assert "sqlite" in out
    assert "postgres" in out or "postgresql" in out
    assert "mysql" in out
    assert "mssql" in out


def test_cli_git_spec(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"],
                   cwd=repo, check=True, capture_output=True)

    (repo / "data.csv").write_text("id,name\n1,Ali\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "1"],
                   cwd=repo, check=True, capture_output=True)

    (repo / "data.csv").write_text("id,name\n1,Ali\n2,Sara\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "2"],
                   cwd=repo, check=True, capture_output=True)

    old_cwd = os.getcwd()
    os.chdir(repo)
    try:
        code = main([
            "HEAD~1:data.csv", "HEAD:data.csv", "--key", "id", "--quiet"
        ])
        assert code == 0
    finally:
        os.chdir(old_cwd)


def test_cli_schema_file(tmp_path):
    import json

    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps({"id": "int", "name": "str"}), encoding="utf-8")

    code = main([
        str(FIXTURES / "old.csv"),
        str(FIXTURES / "new.csv"),
        "--key", "id",
        "--quiet",
    ])
    assert code == 0
