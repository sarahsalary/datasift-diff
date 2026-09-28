# Git Revisions

Diff against any git revision using the `<rev>:<path>` syntax.

## Examples

```bash
# Compare current file with its parent commit
datasift-diff HEAD~1:data.csv data.csv --key id

# Compare two branches
datasift-diff main:users.parquet HEAD:users.parquet --key user_id

# Compare a tag with HEAD
datasift-diff v1.0.0:data/users.json HEAD:data/users.json --key id
```

Format is detected from the extension after the colon. Works with any
format supported by the plugin system.

## Python API

```python
from datasift_diff import diff

result = diff("HEAD~1:data.csv", "HEAD:data.csv", key="id")
```

## Detecting Git Specs

```python
from datasift_diff.git import is_git_spec, read_from_git, resolve_git_ref

assert is_git_spec("HEAD:data.csv") is True
assert is_git_spec("s3://bucket/key") is False

data = read_from_git("HEAD:data.csv")
sha = resolve_git_ref("HEAD")
```