# Database Support

`datasift-diff` can read rows directly from SQL databases and diff them
without exporting to CSV/JSON first.

## Supported Databases

| Scheme | Driver | Install |
|--------|--------|---------|
| `sqlite://` | stdlib `sqlite3` | — |
| `postgres://` | `psycopg` | `pip install datasift-diff[postgres]` |
| `mysql://` | `PyMySQL` | `pip install datasift-diff[mysql]` |
| `mssql://` | `pyodbc` | `pip install datasift-diff[mssql]` |

Install all at once:

```bash
pip install datasift-diff[db]
```

## URI Format

```
<scheme>://<user>:<password>@<host>:<port>/<database>?<options>
```

### SQLite

```
sqlite:///path/to/file.db
sqlite://:memory:
```

### PostgreSQL

```
postgres://user:pass@localhost:5432/mydb
postgresql://user:pass@host/db?sslmode=require
```

### MySQL

```
mysql://user:pass@localhost:3306/mydb
```

### MSSQL

```
mssql://user:pass@localhost:1433/mydb
```

## Query Options

| Option | Description | Example |
|--------|-------------|---------|
| `table` | Table name | `?table=users` |
| `query` | Custom SQL (URL-encoded) | `?query=SELECT%20...` |
| `columns` | Comma-separated column list | `?columns=id,name` |
| `where` | WHERE clause (URL-encoded) | `?where=active%3Dtrue` |
| `order_by` | ORDER BY clause | `?order_by=created_at` |
| `limit` | Row limit | `?limit=10000` |
| `key` | Convenience: also sets diff key | `?key=user_id` |

## CLI Examples

```bash
# Diff two tables in different databases
datasift-diff \
  'postgres://user:pass@prod/db?table=users' \
  'postgres://user:pass@staging/db?table=users' \
  --key user_id

# Compare a table against a snapshot
datasift-diff \
  'postgres://user:pass@host/db?table=users' \
  snapshots/users.csv \
  --key user_id

# SQLite
datasift-diff \
  'sqlite:///old.db?table=users' \
  'sqlite:///new.db?table=users' \
  --key id
```

## Python API

```python
from datasift_diff import diff
from datasift_diff.uri import stream_rows

result = diff(
    "postgres://user:pass@host/db?table=users",
    "postgres://user:pass@host/db?table=users_old",
    key="user_id",
)

for row in stream_rows("postgres://user:pass@host/db?table=users"):
    print(row)
```

## SQL Injection

The `table`, `columns`, `where`, and `order_by` options are inserted into
SQL directly. **Never pass untrusted input** through these options.