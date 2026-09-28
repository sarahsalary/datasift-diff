"""Tests for the FastAPI web UI."""

from __future__ import annotations

import io

import pytest


@pytest.fixture
def client():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    from datasift_diff.web import create_app

    app = create_app()
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_index_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "datasift-diff" in resp.text


def test_api_diff(client):
    old = io.BytesIO(b"id,name\n1,Ali\n2,Sara\n")
    new = io.BytesIO(b"id,name\n1,Ali Reza\n3,Hassan\n")

    resp = client.post(
        "/api/diff",
        files={
            "old": ("old.csv", old, "text/csv"),
            "new": ("new.csv", new, "text/csv"),
        },
        data={"key": "id"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["added"] == 1
    assert data["summary"]["removed"] == 1
    assert data["summary"]["changed"] == 1


def test_api_diff_multi_key(client):
    old = io.BytesIO(b"user_id,date,v\n1,2025-01-01,a\n1,2025-01-02,b\n")
    new = io.BytesIO(b"user_id,date,v\n1,2025-01-01,a\n1,2025-01-02,B\n")

    resp = client.post(
        "/api/diff",
        files={
            "old": ("old.csv", old, "text/csv"),
            "new": ("new.csv", new, "text/csv"),
        },
        data={"key": "user_id,date"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_multi_key"] is True
    assert data["summary"]["changed"] == 1


def test_api_report_returns_html(client):
    old = io.BytesIO(b"id,name\n1,Ali\n")
    new = io.BytesIO(b"id,name\n1,Ali Reza\n")

    resp = client.post(
        "/api/report",
        files={
            "old": ("old.csv", old, "text/csv"),
            "new": ("new.csv", new, "text/csv"),
        },
        data={"key": "id"},
    )
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text
    assert "datasift-diff report" in resp.text
