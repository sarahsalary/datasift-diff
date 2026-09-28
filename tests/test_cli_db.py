"""Integration tests for DB-backed CLI usage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from datasift_diff.cli import main


@pytest.fixture
def two_dbs(tmp_path: Path):
    old_db = tmp_path / "old.db"
    new_db = tmp_path / "new.db"

    for path, rows in [
        (old_db, [(1, "Ali", 30.0), (2, "Sara", 25.0)]),
        (new_db, [(1, "Ali", 31.0), (3, "Reza", 40.0)]),
    ]:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT, age REAL)")
        conn.executemany("INSERT INTO users VALUES (?, ?, ?)", rows)
        conn.commit()
        conn.close()

    return old_db, new_db


def test_cli_db_diff(two_dbs, capsys):
    old_db, new_db = two_dbs
    old_uri = f"sqlite:///{old_db}?table=users"
    new_uri = f"sqlite:///{new_db}?table=users"

    code = main([old_uri, new_uri, "--key", "id", "--format", "json"])
    assert code == 0

    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert data["summary"]["added"] == 1
    assert data["summary"]["removed"] == 1
    assert data["summary"]["changed"] == 1


def test_cli_db_fail_on_change(two_dbs):
    old_db, new_db = two_dbs
    old_uri = f"sqlite:///{old_db}?table=users"
    new_uri = f"sqlite:///{new_db}?table=users"

    code = main([old_uri, new_uri, "--key", "id", "--quiet", "--fail-on-change"])
    assert code == 1


def test_cli_list_schemes_includes_db(capsys):
    code = main(["--list-schemes"])
    assert code == 0
    captured = capsys.readouterr()
    assert "sqlite" in captured.out
    assert "postgres" in captured.out or "postgresql" in captured.out
    assert "mysql" in captured.out
