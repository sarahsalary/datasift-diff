"""Watch mode: re-run diff on file changes."""

from __future__ import annotations

import os
import time
from pathlib import Path

from datasift_diff.core import diff
from datasift_diff.reporters import render


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def watch(
    old: str,
    new: str,
    *,
    key: list[str],
    interval: float = 1.0,
    ignore_fields: list[str] | None = None,
    tolerance: float | None = None,
    flatten: bool = False,
    output_format: str = "text",
    clear: bool = True,
) -> int:
    print(f"Watching {old} and {new} every {interval}s. Ctrl+C to stop.")
    last_old = _mtime(old)
    last_new = _mtime(new)

    try:
        while True:
            time.sleep(interval)
            cur_old = _mtime(old)
            cur_new = _mtime(new)
            if cur_old == last_old and cur_new == last_new:
                continue
            last_old, last_new = cur_old, cur_new

            if clear:
                os.system("cls" if os.name == "nt" else "clear")

            try:
                result = diff(
                    old, new, key=key,
                    ignore_fields=ignore_fields,
                    tolerance=tolerance,
                    flatten=flatten,
                )
                print(render(result, fmt=output_format))
            except Exception as e:
                print(f"error: {e}")
    except KeyboardInterrupt:
        return 0