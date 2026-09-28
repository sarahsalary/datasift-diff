"""Database source plugins for postgres://, mysql://, sqlite://, mssql://."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from datasift_diff.sources.base import RowStreamSource


def _parse_db_uri(uri: str) -> dict[str, Any]:
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()

    if scheme == "sqlite":
        path = parsed.path
        if parsed.netloc and parsed.netloc != "":
            path = parsed.netloc + path
        if not path and parsed.netloc == "":
            path = ":memory:"
        return {"scheme": scheme, "database": path or ":memory:"}

    params = {
        "scheme": scheme,
        "username": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname or "localhost",
        "port": parsed.port,
        "database": parsed.path.lstrip("/") or None,
    }

    if parsed.query:
        params["options"] = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(parsed.query).items()
        }
    return params


def _build_sql_query(
    table: str | None = None,
    query: str | None = None,
    columns: list[str] | None = None,
    where: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> str:
    if query:
        return query

    if not table:
        raise ValueError("Either 'table' or 'query' must be provided.")

    cols = ", ".join(columns) if columns else "*"
    sql = f"SELECT {cols} FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"
    return sql


# ---------------------------------------------------------------------------
# Lazy import helpers (mockable in tests)
# ---------------------------------------------------------------------------


def _import_psycopg():
    """Import psycopg or raise ImportError with a helpful message."""
    try:
        import psycopg  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "PostgreSQL support requires psycopg. "
            "Install with: pip install datasift-diff[postgres]"
        ) from e
    return psycopg


def _import_pymysql():
    """Import pymysql or raise ImportError with a helpful message."""
    try:
        import pymysql  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "MySQL support requires PyMySQL. "
            "Install with: pip install datasift-diff[mysql]"
        ) from e
    return pymysql


def _import_pyodbc():
    """Import pyodbc or raise ImportError with a helpful message."""
    try:
        import pyodbc  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "MSSQL support requires pyodbc. "
            "Install with: pip install datasift-diff[mssql]"
        ) from e
    return pyodbc


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------


class SqliteSource(RowStreamSource):
    scheme = "sqlite"

    def fetch_rows(
        self,
        uri: str,
        *,
        table: str | None = None,
        query: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        params = _parse_db_uri(uri)
        sql = _build_sql_query(table, query, columns, where, order_by, limit)

        conn = sqlite3.connect(params["database"])
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            col_names = [d[0] for d in cursor.description]
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                for row in rows:
                    yield {name: row[name] for name in col_names}
        finally:
            conn.close()

    def fetch(self, uri: str) -> bytes:
        rows = list(self.fetch_rows(uri))
        return json.dumps(rows, default=str).encode("utf-8")

    def exists(self, uri: str) -> bool:
        try:
            params = _parse_db_uri(uri)
            conn = sqlite3.connect(params["database"])
            conn.close()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class PostgresSource(RowStreamSource):
    scheme = "postgres"

    def __init__(self) -> None:
        # Instantiate the driver check so ImportError surfaces at
        # construction time, not on first query.
        _import_psycopg()

    def fetch_rows(
        self,
        uri: str,
        *,
        table: str | None = None,
        query: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        psycopg = _import_psycopg()

        params = _parse_db_uri(uri)
        sql = _build_sql_query(table, query, columns, where, order_by, limit)

        conninfo = (
            f"host={params['host']} "
            f"port={params['port'] or 5432} "
            f"dbname={params['database']} "
        )
        if params["username"]:
            conninfo += f"user={params['username']} "
        if params["password"]:
            conninfo += f"password={params['password']} "
        for key, value in (params.get("options") or {}).items():
            conninfo += f"{key}={value} "

        with psycopg.connect(conninfo) as conn:
            with conn.cursor(name="datasift_diff_cursor") as cursor:
                cursor.itersize = chunk_size
                cursor.execute(sql)
                col_names = [d.name for d in cursor.description]
                for row in cursor:
                    yield dict(zip(col_names, row))

    def fetch(self, uri: str) -> bytes:
        rows = list(self.fetch_rows(uri))
        return json.dumps(rows, default=str).encode("utf-8")

    def exists(self, uri: str) -> bool:
        try:
            psycopg = _import_psycopg()

            params = _parse_db_uri(uri)
            conninfo = (
                f"host={params['host']} port={params['port'] or 5432} "
                f"dbname={params['database']}"
            )
            if params["username"]:
                conninfo += f" user={params['username']}"
            if params["password"]:
                conninfo += f" password={params['password']}"
            with psycopg.connect(conninfo):
                return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------


class MySqlSource(RowStreamSource):
    scheme = "mysql"

    def __init__(self) -> None:
        _import_pymysql()

    def fetch_rows(
        self,
        uri: str,
        *,
        table: str | None = None,
        query: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        pymysql = _import_pymysql()

        params = _parse_db_uri(uri)
        sql = _build_sql_query(table, query, columns, where, order_by, limit)

        conn = pymysql.connect(
            host=params["host"],
            port=params["port"] or 3306,
            user=params["username"],
            password=params["password"],
            database=params["database"],
            cursorclass=pymysql.cursors.SSCursor,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                col_names = [d[0] for d in cursor.description]
                while True:
                    rows = cursor.fetchmany(chunk_size)
                    if not rows:
                        break
                    for row in rows:
                        yield dict(zip(col_names, row))
        finally:
            conn.close()

    def fetch(self, uri: str) -> bytes:
        rows = list(self.fetch_rows(uri))
        return json.dumps(rows, default=str).encode("utf-8")

    def exists(self, uri: str) -> bool:
        try:
            pymysql = _import_pymysql()

            params = _parse_db_uri(uri)
            conn = pymysql.connect(
                host=params["host"],
                port=params["port"] or 3306,
                user=params["username"],
                password=params["password"],
                database=params["database"],
            )
            conn.close()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# MSSQL
# ---------------------------------------------------------------------------


class MssqlSource(RowStreamSource):
    scheme = "mssql"

    def __init__(self) -> None:
        _import_pyodbc()

    def fetch_rows(
        self,
        uri: str,
        *,
        table: str | None = None,
        query: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        pyodbc = _import_pyodbc()

        params = _parse_db_uri(uri)
        sql = _build_sql_query(table, query, columns, where, order_by, limit)

        parts = [
            "DRIVER={ODBC Driver 18 for SQL Server}",
            f"SERVER={params['host']},{params['port'] or 1433}",
            f"DATABASE={params['database']}",
        ]
        if params["username"]:
            parts.append(f"UID={params['username']}")
        if params["password"]:
            parts.append(f"PWD={params['password']}")
        parts.append("TrustServerCertificate=yes")
        conn_str = ";".join(parts)

        conn = pyodbc.connect(conn_str)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            col_names = [d[0] for d in cursor.description]
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                for row in rows:
                    yield dict(zip(col_names, row))
        finally:
            conn.close()

    def fetch(self, uri: str) -> bytes:
        rows = list(self.fetch_rows(uri))
        return json.dumps(rows, default=str).encode("utf-8")

    def exists(self, uri: str) -> bool:
        try:
            pyodbc = _import_pyodbc()

            params = _parse_db_uri(uri)
            conn_str = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={params['host']},{params['port'] or 1433};"
                f"DATABASE={params['database']};"
                f"UID={params['username']};PWD={params['password']};"
                "TrustServerCertificate=yes"
            )
            conn = pyodbc.connect(conn_str)
            conn.close()
            return True
        except Exception:
            return False
