"""Tests for database sources (SQLite works without extras)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from datasift_diff.io import load_data
from datasift_diff.uri import is_db_uri, parse_db_query_params, stream_rows


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT, age REAL)")
    conn.executemany(
        "INSERT INTO users VALUES (?, ?, ?)",
        [(1, "Ali", 30.0), (2, "Sara", 25.0), (3, "Reza", 40.0)],
    )
    conn.commit()
    conn.close()
    return db_path


def test_is_db_uri():
    assert is_db_uri("postgres://user:pass@host/db") is True
    assert is_db_uri("mysql://user:pass@host/db") is True
    assert is_db_uri("sqlite:///path/to.db") is True
    assert is_db_uri("mssql://user:pass@host/db") is True
    assert is_db_uri("s3://bucket/key") is False
    assert is_db_uri("data.csv") is False


def test_parse_db_query_params():
    uri = "postgres://h/db?table=users&limit=100&key=id"
    params = parse_db_query_params(uri)
    assert params["table"] == "users"
    assert params["limit"] == 100
    assert params["key"] == "id"


def test_sqlite_stream_rows(sqlite_db: Path):
    uri = f"sqlite:///{sqlite_db}?table=users"
    rows = list(stream_rows(uri))
    assert len(rows) == 3
    assert rows[0]["name"] == "Ali"
    assert rows[0]["age"] == 30.0


def test_sqlite_load_data(sqlite_db: Path):
    uri = f"sqlite:///{sqlite_db}?table=users"
    records = load_data(uri)
    assert len(records) == 3


def test_sqlite_custom_query(sqlite_db: Path):
    from urllib.parse import quote

    query = quote("SELECT id, name FROM users WHERE age > 26")
    uri = f"sqlite:///{sqlite_db}?query={query}"
    rows = list(stream_rows(uri))
    assert len(rows) == 2
    assert "age" not in rows[0]


def test_sqlite_columns_selection(sqlite_db: Path):
    uri = f"sqlite:///{sqlite_db}?table=users&columns=id,name"
    rows = list(stream_rows(uri))
    assert set(rows[0].keys()) == {"id", "name"}


def test_sqlite_where_order_limit(sqlite_db: Path):
    uri = f"sqlite:///{sqlite_db}?table=users&where=age%20%3E%2026&order_by=age&limit=1"
    rows = list(stream_rows(uri))
    assert len(rows) == 1
    assert rows[0]["name"] == "Ali"


def test_postgres_requires_psycopg(monkeypatch):
    """PostgresSource() must raise ImportError when psycopg is missing."""
    from datasift_diff.sources import db_source

    def fake_import_psycopg():
        raise ImportError(
            "PostgreSQL support requires psycopg. "
            "Install with: pip install datasift-diff[postgres]"
        )

    monkeypatch.setattr(db_source, "_import_psycopg", fake_import_psycopg)

    with pytest.raises(ImportError, match="psycopg"):
        db_source.PostgresSource()


def test_mysql_requires_pymysql(monkeypatch):
    """MySqlSource() must raise ImportError when pymysql is missing."""
    from datasift_diff.sources import db_source

    def fake_import_pymysql():
        raise ImportError(
            "MySQL support requires PyMySQL. "
            "Install with: pip install datasift-diff[mysql]"
        )

    monkeypatch.setattr(db_source, "_import_pymysql", fake_import_pymysql)

    with pytest.raises(ImportError, match="PyMySQL"):
        db_source.MySqlSource()


def test_mssql_requires_pyodbc(monkeypatch):
    """MssqlSource() must raise ImportError when pyodbc is missing."""
    from datasift_diff.sources import db_source

    def fake_import_pyodbc():
        raise ImportError(
            "MSSQL support requires pyodbc. "
            "Install with: pip install datasift-diff[mssql]"
        )

    monkeypatch.setattr(db_source, "_import_pyodbc", fake_import_pyodbc)

    with pytest.raises(ImportError, match="pyodbc"):
        db_source.MssqlSource()
