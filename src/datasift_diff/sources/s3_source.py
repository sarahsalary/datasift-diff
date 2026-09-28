"""S3 source plugin with Range request streaming. Requires boto3."""

from __future__ import annotations

from typing import Iterator


class S3Source:
    scheme = "s3"

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise ImportError(
                    "S3 support requires boto3. "
                    "Install with: pip install datasift-diff[s3]"
                ) from e
            self._client = boto3.client("s3")
        return self._client

    def fetch(self, uri: str) -> bytes:
        bucket, key = self._parse(uri)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            raise IOError(f"Failed to fetch {uri}: {e}") from e

    def fetch_range(self, uri: str, start: int, end: int) -> bytes:
        bucket, key = self._parse(uri)
        client = self._get_client()
        try:
            resp = client.get_object(
                Bucket=bucket, Key=key, Range=f"bytes={start}-{end}"
            )
            return resp["Body"].read()
        except Exception as e:
            raise IOError(f"Failed to fetch range {start}-{end} of {uri}: {e}") from e

    def size(self, uri: str) -> int | None:
        bucket, key = self._parse(uri)
        client = self._get_client()
        try:
            resp = client.head_object(Bucket=bucket, Key=key)
            return int(resp["ContentLength"])
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
        bucket, key = self._parse(uri)
        client = self._get_client()
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def _parse(self, uri: str) -> tuple[str, str]:
        if not uri.startswith("s3://"):
            raise ValueError(f"Not an s3:// URI: {uri}")
        rest = uri[len("s3://"):]
        if "/" not in rest:
            raise ValueError(f"S3 URI must include a key: {uri}")
        bucket, key = rest.split("/", 1)
        return bucket, key
