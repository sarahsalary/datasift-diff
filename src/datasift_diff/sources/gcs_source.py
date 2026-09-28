"""GCS source plugin with Range request streaming. Requires google-cloud-storage."""

from __future__ import annotations

from typing import Iterator


class GcsSource:
    scheme = "gs"

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as e:
                raise ImportError(
                    "GCS support requires google-cloud-storage. "
                    "Install with: pip install datasift-diff[gcs]"
                ) from e
            self._client = storage.Client()
        return self._client

    def fetch(self, uri: str) -> bytes:
        bucket_name, blob_name = self._parse(uri)
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            return blob.download_as_bytes()
        except Exception as e:
            raise IOError(f"Failed to fetch {uri}: {e}") from e

    def fetch_range(self, uri: str, start: int, end: int) -> bytes:
        bucket_name, blob_name = self._parse(uri)
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            return blob.download_as_bytes(start=start, end=end)
        except Exception as e:
            raise IOError(f"Failed to fetch range {start}-{end} of {uri}: {e}") from e

    def size(self, uri: str) -> int | None:
        bucket_name, blob_name = self._parse(uri)
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            blob.reload()
            return blob.size
        except Exception:
            return None

    def stream_chunks(
        self, uri: str, chunk_size: int = 1024 * 1024
    ) -> Iterator[bytes]:
        total = self.size(uri)
        if total is None:
            yield self.fetch(uri)
            return

        start = 0
        while start < total:
            end = min(start + chunk_size - 1, total - 1)
            chunk = self.fetch_range(uri, start, end)
            if not chunk:
                break
            yield chunk
            start = end + 1

    def exists(self, uri: str) -> bool:
        bucket_name, blob_name = self._parse(uri)
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.exists()

    def _parse(self, uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise ValueError(f"Not a gs:// URI: {uri}")
        rest = uri[len("gs://"):]
        if "/" not in rest:
            raise ValueError(f"GCS URI must include a blob: {uri}")
        bucket, blob = rest.split("/", 1)
        return bucket, blob
