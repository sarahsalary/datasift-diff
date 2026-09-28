"""Tests for remote streaming with Range requests."""

from __future__ import annotations

import pytest


def test_s3_source_has_stream_chunks():
    try:
        import boto3  # noqa: F401
    except ImportError:
        pytest.skip("boto3 not installed")

    from datasift_diff.sources.s3_source import S3Source

    source = S3Source()
    assert hasattr(source, "stream_chunks")
    assert hasattr(source, "fetch_range")
    assert hasattr(source, "size")


def test_gcs_source_has_stream_chunks():
    try:
        from google.cloud import storage  # noqa: F401
    except ImportError:
        pytest.skip("google-cloud-storage not installed")

    from datasift_diff.sources.gcs_source import GcsSource

    source = GcsSource()
    assert hasattr(source, "stream_chunks")
    assert hasattr(source, "fetch_range")
    assert hasattr(source, "size")


def test_stream_uri_with_mock(monkeypatch):
    from datasift_diff.plugins import get_registry
    from datasift_diff.uri import stream_uri

    chunks_yielded = []

    class FakeSource:
        scheme = "fake"

        def fetch(self, uri: str) -> bytes:
            return b"full"

        def stream_chunks(self, uri: str, chunk_size: int = 1024 * 1024):
            chunks_yielded.append(chunk_size)
            yield b"chunk1"
            yield b"chunk2"

        def exists(self, uri: str) -> bool:
            return True

    get_registry().register_source(FakeSource(), override=True)

    chunks = list(stream_uri("fake://x", chunk_size=512))
    assert chunks == [b"chunk1", b"chunk2"]
    assert chunks_yielded == [512]


def test_stream_uri_falls_back_to_fetch(monkeypatch):
    from datasift_diff.plugins import get_registry
    from datasift_diff.uri import stream_uri

    class FakeSource:
        scheme = "fake2"

        def fetch(self, uri: str) -> bytes:
            return b"full-content"

        def exists(self, uri: str) -> bool:
            return True

    get_registry().register_source(FakeSource(), override=True)

    chunks = list(stream_uri("fake2://x"))
    assert chunks == [b"full-content"]