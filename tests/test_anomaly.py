"""Tests for anomaly detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datasift_diff.anomaly import (
    AnomalyDetector,
    AnomalyError,
    HistoryStore,
    load_history_from_runs,
    update_history_from_result,
)
from datasift_diff.core import diff


def test_history_store_record_and_get(tmp_path: Path):
    store = HistoryStore(tmp_path / "h.json")
    store.record("k1", "score", 1.0)
    store.record("k1", "score", 2.0)
    store.record("k2", "score", 3.0)
    assert store.get_history("k1", "score") == [1.0, 2.0]
    assert store.get_history("k2", "score") == [3.0]


def test_history_store_persist(tmp_path: Path):
    path = tmp_path / "h.json"
    store = HistoryStore(path)
    store.record("k", "f", 1.0)
    store.save()

    reloaded = HistoryStore(path)
    assert reloaded.get_history("k", "f") == [1.0]


def test_detector_no_history():
    old = [{"id": 1, "score": 5.0}]
    new = [{"id": 1, "score": 100.0}]
    result = diff(old, new, key="id")

    store = HistoryStore(":memory:")
    detector = AnomalyDetector(threshold=3.0, min_history=5)
    report = detector.detect(result, store)
    assert report.anomalies_found == 0


def test_detector_flags_anomaly():
    old = [{"id": 1, "score": 10.0}]
    new = [{"id": 1, "score": 100.0}]
    result = diff(old, new, key="id")

    store = HistoryStore(":memory:")
    for v in [10.0, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95]:
        store.record("id=1", "score", v)

    detector = AnomalyDetector(threshold=3.0, min_history=5)
    report = detector.detect(result, store)
    assert report.anomalies_found == 1
    assert report.scores[0].is_anomaly
    assert report.scores[0].severity in ("high", "critical")


def test_detector_ignores_normal_change():
    old = [{"id": 1, "score": 10.0}]
    new = [{"id": 1, "score": 10.3}]
    result = diff(old, new, key="id")

    store = HistoryStore(":memory:")
    for v in [10.0, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95]:
        store.record("id=1", "score", v)

    detector = AnomalyDetector(threshold=3.0, min_history=5)
    report = detector.detect(result, store)
    assert report.anomalies_found == 0


def test_detector_iqr_method():
    old = [{"id": 1, "score": 10.0}]
    new = [{"id": 1, "score": 100.0}]
    result = diff(old, new, key="id")

    store = HistoryStore(":memory:")
    for v in [10.0, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95]:
        store.record("id=1", "score", v)

    detector = AnomalyDetector(threshold=3.0, method="iqr", min_history=5)
    report = detector.detect(result, store)
    assert report.anomalies_found == 1


def test_detector_invalid_method():
    with pytest.raises(AnomalyError, match="Unknown method"):
        AnomalyDetector(method="bogus")


def test_detector_invalid_threshold():
    with pytest.raises(AnomalyError, match="positive"):
        AnomalyDetector(threshold=0)


def test_update_history_from_result():
    old = [{"id": 1, "score": 10.0}]
    new = [{"id": 1, "score": 10.5}]
    result = diff(old, new, key="id")

    store = HistoryStore(":memory:")
    count = update_history_from_result(result, store)
    assert count == 1
    assert store.get_history("id=1", "score") == [10.5]


def test_load_history_from_runs(tmp_path: Path):
    run1 = tmp_path / "run1.json"
    run2 = tmp_path / "run2.json"

    run1.write_text(json.dumps({
        "changed": [
            {"key": 1, "key_fields": ["id"], "key_values": [{"field": "id", "value": 1}],
             "field_changes": [{"field": "score", "old_value": 9.0, "new_value": 10.0}]}
        ],
        "added": [],
    }), encoding="utf-8")

    run2.write_text(json.dumps({
        "changed": [
            {"key": 1, "key_fields": ["id"], "key_values": [{"field": "id", "value": 1}],
             "field_changes": [{"field": "score", "old_value": 10.0, "new_value": 11.0}]}
        ],
        "added": [],
    }), encoding="utf-8")

    store = load_history_from_runs([run1, run2])
    history = store.get_history("id=1", "score")
    assert history == [10.0, 11.0]


def test_anomaly_cli_end_to_end(tmp_path: Path, capsys):
    old = tmp_path / "old.csv"
    new = tmp_path / "new.csv"
    history = tmp_path / "history.json"

    old.write_text("id,score\n1,10.0\n", encoding="utf-8")
    new.write_text("id,score\n1,100.0\n", encoding="utf-8")

    h = HistoryStore(history)
    for v in [10.0, 10.1, 9.9, 10.2, 9.8]:
        h.record("id=1", "score", v)
    h.save()

    from datasift_diff.anomaly_cli import main

    code = main([
        str(old), str(new),
        "--key", "id",
        "--history", str(history),
        "--fail-on-anomaly",
    ])
    assert code == 1
    captured = capsys.readouterr()
    assert "Anomaly" in captured.out