"""Statistical anomaly detection for diff results."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from datasift_diff.models import DiffResult


class AnomalyError(Exception):
    """Raised when anomaly detection cannot be performed."""


@dataclass
class AnomalyScore:
    key: str
    field: str
    old_value: Any
    new_value: Any
    z_score: float
    is_anomaly: bool
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "z_score": round(self.z_score, 4),
            "is_anomaly": self.is_anomaly,
            "severity": self.severity,
        }


@dataclass
class AnomalyReport:
    scores: list[AnomalyScore] = field(default_factory=list)
    threshold: float = 3.0
    total_changes: int = 0
    anomalies_found: int = 0
    history_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold": self.threshold,
            "total_changes": self.total_changes,
            "anomalies_found": self.anomalies_found,
            "history_samples": self.history_samples,
            "scores": [s.to_dict() for s in self.scores],
        }

    def summary(self) -> str:
        return (
            f"Anomalies: {self.anomalies_found}/{self.total_changes} "
            f"(threshold={self.threshold}σ, history={self.history_samples} samples)"
        )


def _parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return None
    return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float], mean: float | None = None) -> float:
    if len(values) < 2:
        return 0.0
    if mean is None:
        mean = _mean(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_v[mid - 1] + sorted_v[mid]) / 2
    return sorted_v[mid]


def _iqr(values: list[float]) -> tuple[float, float, float]:
    if len(values) < 4:
        return (0.0, 0.0, 0.0)
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[(3 * n) // 4]
    return (q1, q3, q3 - q1)


def _severity(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= 5:
        return "critical"
    if abs_z >= 4:
        return "high"
    if abs_z >= 3:
        return "medium"
    return "low"


class HistoryStore:
    """Persistent store of historical values per (key, field) pair."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, dict[str, list[float]]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, default=str),
            encoding="utf-8",
        )

    def record(self, key: str, field: str, value: float) -> None:
        self._data.setdefault(key, {}).setdefault(field, []).append(value)

    def get_history(self, key: str, field: str) -> list[float]:
        return list(self._data.get(key, {}).get(field, []))

    def all_histories(self) -> dict[str, dict[str, list[float]]]:
        return self._data

    def clear(self) -> None:
        self._data = {}
        if self.path.exists():
            self.path.unlink()


class AnomalyDetector:
    """Detect anomalous changes in a DiffResult using statistical methods."""

    def __init__(
        self,
        threshold: float = 3.0,
        method: str = "zscore",
        min_history: int = 5,
    ) -> None:
        if method not in ("zscore", "iqr"):
            raise AnomalyError(f"Unknown method '{method}'. Use 'zscore' or 'iqr'.")
        if threshold <= 0:
            raise AnomalyError("threshold must be positive.")
        self.threshold = threshold
        self.method = method
        self.min_history = min_history

    def detect(
        self,
        result: DiffResult,
        history: HistoryStore,
    ) -> AnomalyReport:
        report = AnomalyReport(threshold=self.threshold)
        report.total_changes = result.total_changes
        report.history_samples = sum(
            len(vals)
            for fields in history.all_histories().values()
            for vals in fields.values()
        )

        for change in result.changed:
            key_str = change.key_str()
            for fc in change.field_changes:
                old_num = _parse_number(fc.old_value)
                new_num = _parse_number(fc.new_value)

                if old_num is None or new_num is None:
                    continue

                key_history = history.get_history(key_str, fc.field)
                if len(key_history) < self.min_history:
                    key_history = self._global_history(history, fc.field)

                if len(key_history) < self.min_history:
                    continue

                z = self._score(new_num, key_history)
                is_anomaly = abs(z) > self.threshold
                severity = _severity(z) if is_anomaly else "low"

                report.scores.append(
                    AnomalyScore(
                        key=key_str,
                        field=fc.field,
                        old_value=fc.old_value,
                        new_value=fc.new_value,
                        z_score=z,
                        is_anomaly=is_anomaly,
                        severity=severity,
                    )
                )

        report.anomalies_found = sum(1 for s in report.scores if s.is_anomaly)
        return report

    def _global_history(
        self, history: HistoryStore, field: str
    ) -> list[float]:
        values: list[float] = []
        for fields in history.all_histories().values():
            values.extend(fields.get(field, []))
        return values

    def _score(self, value: float, history: list[float]) -> float:
        if self.method == "zscore":
            mean = _mean(history)
            stdev = _stdev(history, mean)
            if stdev == 0:
                return 0.0
            return (value - mean) / stdev

        q1, q3, iqr = _iqr(history)
        if iqr == 0:
            return 0.0
        return (value - _median(history)) / (iqr / 1.349)


def update_history_from_result(
    result: DiffResult,
    history: HistoryStore,
) -> int:
    """Record the new values from a DiffResult into the history store."""
    count = 0
    for change in result.changed:
        key_str = change.key_str()
        for fc in change.field_changes:
            num = _parse_number(fc.new_value)
            if num is None:
                continue
            history.record(key_str, fc.field, num)
            count += 1

    for change in result.added:
        if not change.new_record:
            continue
        key_str = change.key_str()
        for field, value in change.new_record.items():
            num = _parse_number(value)
            if num is None:
                continue
            history.record(key_str, field, num)
            count += 1

    return count


def load_history_from_runs(
    paths: Iterable[str | Path],
) -> HistoryStore:
    """Build a HistoryStore by replaying a sequence of diff JSON reports."""
    store = HistoryStore(":memory:")
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in data.get("changed", []):
            key = _key_from_dict(record)
            for fc in record.get("field_changes", []):
                num = _parse_number(fc.get("new_value"))
                if num is not None:
                    store.record(key, fc["field"], num)
        for record in data.get("added", []):
            key = _key_from_dict(record)
            new_record = record.get("new_record") or {}
            for field, value in new_record.items():
                num = _parse_number(value)
                if num is not None:
                    store.record(key, field, num)
    return store


def _key_from_dict(record: dict[str, Any]) -> str:
    key_values = record.get("key_values") or []
    if not key_values:
        key = record.get("key")
        if isinstance(key, list):
            key_fields = record.get("key_fields") or [f"k{i}" for i in range(len(key))]
            return "|".join(f"{f}={v}" for f, v in zip(key_fields, key))
        key_fields = record.get("key_fields") or ["key"]
        return f"{key_fields[0]}={key}"
    return "|".join(f"{kv['field']}={kv['value']}" for kv in key_values)