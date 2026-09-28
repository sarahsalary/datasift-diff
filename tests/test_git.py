"""Tests for git revision support."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from datasift_diff.git import (
    GitError,
    git_exists,
    is_git_spec,
    parse_git_spec,
    read_from_git,
    resolve_git_ref,
)


def test_is_git_spec():
    assert is_git_spec("HEAD:data.csv") is True
    assert is_git_spec("main:path/to/file.json") is True
    assert is_git_spec("v1.0.0:users.parquet") is True
    assert is_git_spec("s3://bucket/key") is False
    assert is_git_spec("C:\\path\\file.csv") is False
    assert is_git_spec("data.csv") is False
    assert is_git_spec("https://x.com/y") is False


def test_parse_git_spec():
    assert parse_git_spec("HEAD:data.csv") == ("HEAD", "data.csv")
    assert parse_git_spec("main:a/b/c.json") == ("main", "a/b/c.json")


@pytest.fixture
def git_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )

    (repo / "data.csv").write_text("id,name\n1,Ali\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "first"],
        cwd=repo, check=True, capture_output=True,
    )

    (repo / "data.csv").write_text("id,name\n1,Ali\n2,Sara\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=repo, check=True, capture_output=True,
    )
    return repo


def test_read_from_git_head(git_repo):
    data = read_from_git("HEAD:data.csv", cwd=git_repo)
    assert b"2,Sara" in data


def test_read_from_git_prev(git_repo):
    data = read_from_git("HEAD~1:data.csv", cwd=git_repo)
    assert b"2,Sara" not in data
    assert b"1,Ali" in data


def test_read_missing_path(git_repo):
    with pytest.raises(GitError):
        read_from_git("HEAD:nonexistent.csv", cwd=git_repo)


def test_git_exists(git_repo):
    assert git_exists("HEAD:data.csv", cwd=git_repo) is True
    assert git_exists("HEAD:nope.csv", cwd=git_repo) is False


def test_resolve_git_ref(git_repo):
    sha = resolve_git_ref("HEAD", cwd=git_repo)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)