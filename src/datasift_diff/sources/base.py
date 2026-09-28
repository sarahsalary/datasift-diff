"""Base classes for row-streaming sources."""

from __future__ import annotations

from typing import Any, Iterator


class RowStreamSource:
    """Base class for sources that yield rows as dicts."""

    scheme: str = ""

    def fetch_rows(
        self,
        uri: str,
        *,
        table: str | None = None,
        query: str | None = None,
        columns: list[str] | None = None,
        where: str | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        chunk_size: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def fetch(self, uri: str) -> bytes:
        raise NotImplementedError

    def exists(self, uri: str) -> bool:
        raise NotImplementedError
