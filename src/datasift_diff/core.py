"""Core diff logic: match records by key and compare fields."""

from __future__ import annotations

import re
from typing import Any

from datasift_diff.io import load_records
from datasift_diff.models import Change, DiffResult, FieldChange, KeyValue


class DiffError(Exception):
    """Raised when a diff cannot be computed."""


def _normalize_keys(keys: list[str]) -> list[str]:
    if not keys:
        raise DiffError("At least one key field is required.")
    return [k.strip() for k in keys if k.strip()]


def _get_nested(record: dict[str, Any], path: str) -> Any:
    if "." not in path:
        return record.get(path)
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _flatten(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = value
    return flat


def _record_key(record: dict[str, Any], keys: list[str]) -> tuple[Any, ...]:
    return tuple(_get_nested(record, k) for k in keys)


def _close_enough(a: Any, b: Any, tolerance: float | None) -> bool:
    if tolerance is None:
        return a == b
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= tolerance
    except (TypeError, ValueError):
        return a == b


def _compare_records(
    old: dict[str, Any],
    new: dict[str, Any],
    ignore: set[str],
    tolerance: float | None,
    flatten: bool,
) -> list[FieldChange]:
    if flatten:
        old = _flatten(old)
        new = _flatten(new)

    changes: list[FieldChange] = []
    all_fields = set(old) | set(new)
    for field in sorted(all_fields):
        if field in ignore:
            continue
        ov = old.get(field)
        nv = new.get(field)
        if not _close_enough(ov, nv, tolerance):
            changes.append(FieldChange(field=field, old_value=ov, new_value=nv))
    return changes


def diff(
    old: Any,
    new: Any,
    *,
    key: str | list[str],
    ignore_fields: list[str] | None = None,
    tolerance: float | None = None,
    streaming: bool = False,
    flatten: bool = False,
) -> DiffResult:
    """Compare two datasets by key and return a DiffResult."""
    if isinstance(key, str):
        keys = _normalize_keys([key])
    else:
        keys = _normalize_keys(list(key))

    old_records = load_records(old)
    new_records = load_records(new)

    if streaming:
        return _streaming_diff(
            old_records, new_records, keys, ignore_fields or [],
            tolerance, flatten,
        )

    ignore = set(ignore_fields or [])

    old_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    for rec in old_records:
        k = _record_key(rec, keys)
        if k in old_map:
            raise DiffError(f"Duplicate key {k} in old dataset.")
        old_map[k] = rec

    new_map: dict[tuple[Any, ...], dict[str, Any]] = {}
    for rec in new_records:
        k = _record_key(rec, keys)
        if k in new_map:
            raise DiffError(f"Duplicate key {k} in new dataset.")
        new_map[k] = rec

    result = DiffResult(
        key_fields=keys,
        is_multi_key=len(keys) > 1,
    )

    for k, old_rec in old_map.items():
        if k not in new_map:
            result.removed.append(
                Change(
                    key=_key_value(k, keys),
                    key_fields=keys,
                    key_values=[KeyValue(f, v) for f, v in zip(keys, k)],
                    old_record=old_rec,
                )
            )

    for k, new_rec in new_map.items():
        if k not in old_map:
            result.added.append(
                Change(
                    key=_key_value(k, keys),
                    key_fields=keys,
                    key_values=[KeyValue(f, v) for f, v in zip(keys, k)],
                    new_record=new_rec,
                )
            )

    for k, old_rec in old_map.items():
        if k not in new_map:
            continue
        new_rec = new_map[k]
        changes = _compare_records(
            old_rec, new_rec, ignore, tolerance, flatten
        )
        if changes:
            result.changed.append(
                Change(
                    key=_key_value(k, keys),
                    key_fields=keys,
                    key_values=[KeyValue(f, v) for f, v in zip(keys, k)],
                    old_record=old_rec,
                    new_record=new_rec,
                    field_changes=changes,
                )
            )

    return result


def _key_value(key: tuple[Any, ...], keys: list[str]) -> Any:
    if len(keys) == 1:
        return key[0]
    return list(key)


def _streaming_diff(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    keys: list[str],
    ignore_fields: list[str],
    tolerance: float | None,
    flatten: bool,
) -> DiffResult:
    """Merge-join for sorted inputs."""
    ignore = set(ignore_fields)
    result = DiffResult(key_fields=keys, is_multi_key=len(keys) > 1)

    old_sorted = sorted(old_records, key=lambda r: _record_key(r, keys))
    new_sorted = sorted(new_records, key=lambda r: _record_key(r, keys))

    i = j = 0
    while i < len(old_sorted) and j < len(new_sorted):
        ok = _record_key(old_sorted[i], keys)
        nk = _record_key(new_sorted[j], keys)
        if ok < nk:
            result.removed.append(
                Change(
                    key=_key_value(ok, keys),
                    key_fields=keys,
                    key_values=[KeyValue(f, v) for f, v in zip(keys, ok)],
                    old_record=old_sorted[i],
                )
            )
            i += 1
        elif ok > nk:
            result.added.append(
                Change(
                    key=_key_value(nk, keys),
                    key_fields=keys,
                    key_values=[KeyValue(f, v) for f, v in zip(keys, nk)],
                    new_record=new_sorted[j],
                )
            )
            j += 1
        else:
            changes = _compare_records(
                old_sorted[i], new_sorted[j], ignore, tolerance, flatten
            )
            if changes:
                result.changed.append(
                    Change(
                        key=_key_value(ok, keys),
                        key_fields=keys,
                        key_values=[KeyValue(f, v) for f, v in zip(keys, ok)],
                        old_record=old_sorted[i],
                        new_record=new_sorted[j],
                        field_changes=changes,
                    )
                )
            i += 1
            j += 1

    while i < len(old_sorted):
        ok = _record_key(old_sorted[i], keys)
        result.removed.append(
            Change(
                key=_key_value(ok, keys),
                key_fields=keys,
                key_values=[KeyValue(f, v) for f, v in zip(keys, ok)],
                old_record=old_sorted[i],
            )
        )
        i += 1

    while j < len(new_sorted):
        nk = _record_key(new_sorted[j], keys)
        result.added.append(
            Change(
                key=_key_value(nk, keys),
                key_fields=keys,
                key_values=[KeyValue(f, v) for f, v in zip(keys, nk)],
                new_record=new_sorted[j],
            )
        )
        j += 1

    return result