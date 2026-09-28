"""Textual TUI for browsing diff results."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import DataTable, Footer, Header, Input
    except ImportError:
        print(
            "error: TUI requires textual. "
            "Install with: pip install datasift-diff[tui]",
            file=sys.stderr,
        )
        return 2

    from datasift_diff.core import diff

    parser = argparse.ArgumentParser(
        prog="datasift-diff-tui",
        description="Interactive TUI for datasift-diff.",
    )
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--key", "-k", required=True, action="append")
    parser.add_argument("--ignore", "-i", default="")
    parser.add_argument("--tolerance", "-t", type=float, default=None)
    parser.add_argument("--flatten", action="store_true")
    args = parser.parse_args(argv)

    keys = []
    for raw in args.key:
        for part in raw.split(","):
            part = part.strip()
            if part:
                keys.append(part)

    ignore = [f.strip() for f in args.ignore.split(",") if f.strip()]
    result = diff(
        args.old, args.new, key=keys,
        ignore_fields=ignore,
        tolerance=args.tolerance,
        flatten=args.flatten,
    )

    class DiffApp(App):
        CSS = """
        Screen { layout: vertical; }
        #search { dock: top; height: 3; }
        DataTable { height: 1fr; }
        """

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Filter...", id="search")
            yield DataTable()
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            table.add_columns("Type", "Key", "Field", "Old", "New")
            for change in result.added:
                table.add_row("added", change.key_str(), "", "", "")
            for change in result.removed:
                table.add_row("removed", change.key_str(), "", "", "")
            for change in result.changed:
                for fc in change.field_changes:
                    table.add_row(
                        "changed", change.key_str(),
                        fc.field, str(fc.old_value), str(fc.new_value),
                    )

        def on_input_changed(self, event: Input.Changed) -> None:
            table = self.query_one(DataTable)
            table.clear()
            q = event.value.lower()
            for change in result.added:
                key = change.key_str()
                if not q or q in key.lower():
                    table.add_row("added", key, "", "", "")
            for change in result.removed:
                key = change.key_str()
                if not q or q in key.lower():
                    table.add_row("removed", key, "", "", "")
            for change in result.changed:
                for fc in change.field_changes:
                    key = change.key_str()
                    if not q or q in key.lower() or q in fc.field.lower():
                        table.add_row(
                            "changed", key, fc.field,
                            str(fc.old_value), str(fc.new_value),
                        )

    DiffApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())