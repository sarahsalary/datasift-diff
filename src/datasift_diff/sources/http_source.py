"""HTTP/HTTPS source plugin (no extra dependencies)."""

from __future__ import annotations

import urllib.request


class HttpSource:
    scheme = "http"

    def fetch(self, uri: str) -> bytes:
        with urllib.request.urlopen(uri) as resp:
            return resp.read()

    def exists(self, uri: str) -> bool:
        try:
            req = urllib.request.Request(uri, method="HEAD")
            with urllib.request.urlopen(req):
                return True
        except Exception:
            return False