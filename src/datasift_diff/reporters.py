"""Output reporters: text, JSON, CSV, HTML."""

from __future__ import annotations

import csv
import io
import json

from datasift_diff.models import DiffResult


def render_text(result: DiffResult) -> str:
    lines: list[str] = []
    s = result.summary
    lines.append("=" * 60)
    lines.append("datasift-diff report")
    lines.append("=" * 60)
    lines.append(
        f"Key(s): {', '.join(result.key_fields)}"
        + (" (multi-key)" if result.is_multi_key else "")
    )
    lines.append(
        f"Added: {s.added}   Removed: {s.removed}   Changed: {s.changed}"
    )
    lines.append("")

    if not result.has_changes:
        lines.append("No changes.")
        return "\n".join(lines)

    if result.added:
        lines.append("-" * 60)
        lines.append(f"ADDED ({len(result.added)})")
        lines.append("-" * 60)
        for change in result.added:
            lines.append(f"  + {change.key_str()}")
        lines.append("")

    if result.removed:
        lines.append("-" * 60)
        lines.append(f"REMOVED ({len(result.removed)})")
        lines.append("-" * 60)
        for change in result.removed:
            lines.append(f"  - {change.key_str()}")
        lines.append("")

    if result.changed:
        lines.append("-" * 60)
        lines.append(f"CHANGED ({len(result.changed)})")
        lines.append("-" * 60)
        for change in result.changed:
            lines.append(f"  ~ {change.key_str()}")
            for fc in change.field_changes:
                lines.append(
                    f"      {fc.field}: {fc.old_value!r} -> {fc.new_value!r}"
                )

    return "\n".join(lines)


def render_json(result: DiffResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str)


def render_csv(result: DiffResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["change", "key", "field", "old_value", "new_value"])

    for change in result.added:
        writer.writerow(["added", change.key_str(), "", "", ""])
    for change in result.removed:
        writer.writerow(["removed", change.key_str(), "", "", ""])
    for change in result.changed:
        for fc in change.field_changes:
            writer.writerow(
                ["changed", change.key_str(), fc.field, fc.old_value, fc.new_value]
            )

    return buf.getvalue()


def render(result: DiffResult, fmt: str = "text") -> str:
    if fmt == "text":
        return render_text(result)
    if fmt == "json":
        return render_json(result)
    if fmt == "csv":
        return render_csv(result)
    if fmt == "html":
        from datasift_diff.html_report import render_html

        return render_html(result)
    raise ValueError(f"Unknown format: {fmt}")
