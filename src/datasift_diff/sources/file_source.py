"""Local file source plugin."""

from __future__ import annotations

from pathlib import Path


class FileSource:
    scheme = "file"

    def fetch(self, uri: str) -> bytes:
        path = uri
        if uri.startswith("file://"):
            path = uri[len("file://"):]
        return Path(path).read_bytes()

    def exists(self, uri: str) -> bool:
        path = uri
        if uri.startswith("file://"):
            path = uri[len("file://"):]
        return Path(path).exists()