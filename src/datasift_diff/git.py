"""Read files from git revisions (e.g. old:data.csv)."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""


def is_git_spec(spec: str) -> bool:
    """
    Return True if the string looks like a git revision spec.

    A git spec has the form `<rev>:<path>` where `<rev>` doesn't contain
    a slash followed by another slash (which would indicate a URI).

    Examples:
        'HEAD:data.csv'          -> True
        'main:path/to/file.csv'  -> True
        'v1.0.0:data/users.json' -> True
        's3://bucket/key'        -> False (has ://)
        'C:\\path\\file.csv'     -> False (Windows drive)
        'data.csv'               -> False (no colon)
    """
    if "://" in spec:
        return False
    if len(spec) >= 2 and spec[1] == ":" and spec[0].isalpha():
        if len(spec) >= 3 and spec[2] in ("\\", "/"):
            return False
    if ":" not in spec:
        return False
    rev, _, path = spec.partition(":")
    if not rev or not path:
        return False
    if any(c in rev for c in " \t\n\r"):
        return False
    return True


def parse_git_spec(spec: str) -> tuple[str, str]:
    """Split 'rev:path' into (rev, path)."""
    rev, _, path = spec.partition(":")
    return rev, path


def _run_git(args: list[str], cwd: str | Path | None = None) -> bytes:
    """Run a git command and return stdout, raising GitError on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise GitError("git executable not found on PATH.") from e

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {stderr}")

    return result.stdout


def read_from_git(spec: str, cwd: str | Path | None = None) -> bytes:
    """Read the contents of a file at a specific git revision."""
    rev, path = parse_git_spec(spec)
    return _run_git(["show", f"{rev}:{path}"], cwd=cwd)


def git_exists(spec: str, cwd: str | Path | None = None) -> bool:
    """Check if a git spec resolves to an existing blob."""
    try:
        read_from_git(spec, cwd=cwd)
        return True
    except GitError:
        return False


def resolve_git_ref(ref: str, cwd: str | Path | None = None) -> str:
    """Resolve a ref (e.g. 'HEAD', 'main') to a commit SHA."""
    try:
        out = _run_git(["rev-parse", ref], cwd=cwd)
        return out.decode("utf-8").strip()
    except GitError as e:
        raise GitError(f"Cannot resolve ref '{ref}': {e}") from e