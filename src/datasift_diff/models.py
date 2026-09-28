"""Data models for diff results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldChange:
    field: str
    old_value: Any
    new_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }


@dataclass
class KeyValue:
    field: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value}


@dataclass
class Change:
    key: Any
    key_fields: list[str]
    key_values: list[KeyValue] = field(default_factory=list)
    old_record: dict[str, Any] | None = None
    new_record: dict[str, Any] | None = None
    field_changes: list[FieldChange] = field(default_factory=list)

    def key_str(self) -> str:
        if self.key_values:
            return "|".join(f"{kv.field}={kv.value}" for kv in self.key_values)
        if isinstance(self.key, list):
            return "|".join(
                f"{f}={v}" for f, v in zip(self.key_fields, self.key)
            )
        return f"{self.key_fields[0]}={self.key}" if self.key_fields else str(self.key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "key_fields": self.key_fields,
            "key_values": [kv.to_dict() for kv in self.key_values],
            "old_record": self.old_record,
            "new_record": self.new_record,
            "field_changes": [fc.to_dict() for fc in self.field_changes],
        }


@dataclass
class DiffSummary:
    added: int = 0
    removed: int = 0
    changed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
        }


@dataclass
class DiffResult:
    added: list[Change] = field(default_factory=list)
    removed: list[Change] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    key_fields: list[str] = field(default_factory=list)
    is_multi_key: bool = False

    @property
    def summary(self) -> DiffSummary:
        return DiffSummary(
            added=len(self.added),
            removed=len(self.removed),
            changed=len(self.changed),
        )

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "total_changes": self.total_changes,
            "has_changes": self.has_changes,
            "key_fields": self.key_fields,
            "is_multi_key": self.is_multi_key,
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "changed": [c.to_dict() for c in self.changed],
        }
