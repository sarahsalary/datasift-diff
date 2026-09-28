"""Tests for core diff logic."""

from __future__ import annotations

import pytest

from datasift_diff.core import DiffError, diff


def test_basic_diff():
    old = [{"id": 1, "name": "Ali"}, {"id": 2, "name": "Sara"}]
    new = [{"id": 1, "name": "Ali Reza"}, {"id": 3, "name": "Hassan"}]
    result = diff(old, new, key="id")
    s = result.summary
    assert s.added == 1
    assert s.removed == 1
    assert s.changed == 1


def test_multi_key():
    old = [
        {"user_id": 1, "date": "2025-01-01", "v": "a"},
        {"user_id": 1, "date": "2025-01-02", "v": "b"},
    ]
    new = [
        {"user_id": 1, "date": "2025-01-01", "v": "a"},
        {"user_id": 1, "date": "2025-01-02", "v": "B"},
    ]
    result = diff(old, new, key=["user_id", "date"])
    assert result.is_multi_key is True
    assert result.summary.changed == 1


def test_numeric_tolerance():
    old = [{"id": 1, "v": 1.0000001}]
    new = [{"id": 1, "v": 1.0000002}]
    result = diff(old, new, key="id", tolerance=1e-6)
    assert result.summary.changed == 0


def test_nested_key():
    old = [{"user": {"id": 1}, "name": "Ali"}]
    new = [{"user": {"id": 1}, "name": "Ali Reza"}]
    result = diff(old, new, key="user.id")
    assert result.summary.changed == 1


def test_flatten():
    old = [{"id": 1, "user": {"name": "Ali"}}]
    new = [{"id": 1, "user": {"name": "Ali Reza"}}]
    result = diff(old, new, key="id", flatten=True)
    assert result.summary.changed == 1
    assert result.changed[0].field_changes[0].field == "user.name"


def test_ignore_fields():
    old = [{"id": 1, "name": "Ali", "updated_at": "2025-01-01"}]
    new = [{"id": 1, "name": "Ali", "updated_at": "2025-02-01"}]
    result = diff(old, new, key="id", ignore_fields=["updated_at"])
    assert result.summary.changed == 0


def test_duplicate_key():
    old = [{"id": 1}, {"id": 1}]
    new = [{"id": 1}]
    with pytest.raises(DiffError, match="Duplicate key"):
        diff(old, new, key="id")


def test_streaming():
    old = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
    new = [{"id": 1, "v": "a"}, {"id": 3, "v": "c"}]
    result = diff(old, new, key="id", streaming=True)
    s = result.summary
    assert s.added == 1
    assert s.removed == 1
