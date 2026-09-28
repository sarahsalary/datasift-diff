"""Command-line interface for datasift-diff."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datasift_diff import __version__
from datasift_diff.core import DiffError, _normalize_keys, diff
from datasift_diff.io import DataLoadError, load_records
from datasift_diff.plugins import get_registry
from datasift_diff.reporters import render

EXIT_NO_CHANGES = 0
EXIT_CHANGES_FOUND = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datasift-diff",
        description=(
            "Compare two datasets (files, remote URIs, git revisions, "
            "or databases) by key."
        ),
        epilog=(
            "Examples:\n"
            "  datasift-diff old.csv new.csv --key id\n"
            "  datasift-diff HEAD~1:data.csv data.csv --key id\n"
            "  datasift-diff s3://bucket/v1.csv s3://bucket/v2.csv --key id\n"
            "  datasift-diff 'postgres://user:pass@host/db?table=users' \\\n"
            "                'postgres://user:pass@host/db?table=users_old' --key id\n"
            "  datasift-diff old.csv new.csv --key id --anomaly-threshold 3.5 \\\n"
            "      --anomaly-history history.json --anomaly-update\n"
            "  datasift-diff --list-formats\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("old", nargs="?", help="Old dataset.")
    parser.add_argument("new", nargs="?", help="New dataset.")
    parser.add_argument("--key", "-k", action="append",
                        help="Key field(s). Repeat or comma-separate.")
    parser.add_argument("--format", "-f",
                        choices=["text", "json", "csv", "html"],
                        default="text", help="Output format (default: text).")
    parser.add_argument("--output", "-o", help="Write output to a file.")
    parser.add_argument("--ignore", "-i", default="",
                        help="Comma-separated fields to ignore.")
    parser.add_argument("--tolerance", "-t", type=float, default=None,
                        help="Numeric tolerance for float comparison.")
    parser.add_argument("--streaming", action="store_true",
                        help="Single-pass merge-join for sorted inputs.")
    parser.add_argument("--flatten", action="store_true",
                        help="Flatten nested dicts before comparison.")
    parser.add_argument("--validate", action="store_true",
                        help="Validate both datasets with datasift-py first.")
    parser.add_argument("--schema-file",
                        help="Schema file (.json, .yaml, .toml) for --validate.")
    parser.add_argument("--watch", action="store_true",
                        help="Watch files and re-run diff on changes.")
    parser.add_argument("--watch-interval", type=float, default=1.0,
                        help="Polling interval for --watch (default: 1.0s).")
    parser.add_argument("--watch-no-clear", action="store_true",
                        help="Do not clear screen between watch iterations.")

    parser.add_argument("--anomaly-history",
                        help="Path to an anomaly history JSON file.")
    parser.add_argument("--anomaly-threshold", type=float, default=3.0,
                        help="Z-score threshold (default: 3.0).")
    parser.add_argument("--anomaly-method", choices=["zscore", "iqr"],
                        default="zscore",
                        help="Detection method (default: zscore).")
    parser.add_argument("--anomaly-min-history", type=int, default=5,
                        help="Minimum history samples (default: 5).")
    parser.add_argument("--anomaly-update", action="store_true",
                        help="Record new values into history after analysis.")
    parser.add_argument("--fail-on-anomaly", action="store_true",
                        help="Exit 1 if any anomalies are found.")

    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress output.")
    parser.add_argument("--fail-on-change", action="store_true",
                        help="Exit 1 if changes found.")
    parser.add_argument("--list-formats", action="store_true",
                        help="List registered format plugins and exit.")
    parser.add_argument("--list-schemes", action="store_true",
                        help="List registered URI schemes and exit.")
    parser.add_argument("--version", action="version",
                        version=f"datasift-diff {__version__}")
    return parser


def _collect_keys(args_keys: list[str] | None) -> list[str]:
    if not args_keys:
        return []
    out: list[str] = []
    for raw in args_keys:
        for part in raw.split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _cmd_list_formats() -> int:
    registry = get_registry()
    print("Registered formats:")
    for name in registry.list_formats():
        plugin = registry.get_format(name)
        print(f"  {name:10s}  ({', '.join(plugin.extensions)})")
    return 0


def _cmd_list_schemes() -> int:
    registry = get_registry()
    print("Registered URI schemes:")
    for scheme in registry.list_schemes():
        print(f"  {scheme}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_formats:
        return _cmd_list_formats()
    if args.list_schemes:
        return _cmd_list_schemes()

    if not args.old or not args.new:
        parser.error("'old' and 'new' are required.")
    if not args.key:
        parser.error("--key is required.")

    try:
        keys = _normalize_keys(_collect_keys(args.key))
    except DiffError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR

    ignore_fields = [f.strip() for f in args.ignore.split(",") if f.strip()]

    if args.watch:
        from datasift_diff.watch import watch
        return watch(
            args.old, args.new, key=list(keys),
            interval=args.watch_interval,
            ignore_fields=ignore_fields,
            tolerance=args.tolerance,
            flatten=args.flatten,
            output_format=args.format,
            clear=not args.watch_no_clear,
        )

    if args.validate:
        try:
            from datasift_diff.validation import (
                ValidationError,
                validate_before_diff,
            )
            old_records = load_records(args.old)
            new_records = load_records(args.new)
            validate_before_diff(old_records, new_records, schema_file=args.schema_file)
        except ImportError:
            print("error: --validate requires datasift-py. "
                  "Install: pip install datasift-diff[datasift]", file=sys.stderr)
            return EXIT_ERROR
        except (ValidationError, Exception) as e:
            print(f"error: {e}", file=sys.stderr)
            return EXIT_ERROR

    try:
        result = diff(
            args.old, args.new, key=keys,
            ignore_fields=ignore_fields,
            tolerance=args.tolerance,
            streaming=args.streaming,
            flatten=args.flatten,
        )
    except (DataLoadError, DiffError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR

    output = render(result, fmt=args.format)

    if not args.quiet:
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(output)

    anomaly_exit = 0
    if args.anomaly_history:
        try:
            from datasift_diff.anomaly import (
                AnomalyDetector,
                AnomalyError,
                HistoryStore,
                update_history_from_result,
            )
            history = HistoryStore(args.anomaly_history)
            detector = AnomalyDetector(
                threshold=args.anomaly_threshold,
                method=args.anomaly_method,
                min_history=args.anomaly_min_history,
            )
            report = detector.detect(result, history)

            if not args.quiet:
                print()
                print(report.summary())
                flagged = [s for s in report.scores if s.is_anomaly]
                for s in flagged[:20]:
                    print(f"  [{s.severity.upper()}] {s.key} {s.field}: "
                          f"{s.old_value} -> {s.new_value} (z={s.z_score:+.2f})")
                if len(flagged) > 20:
                    print(f"  ... and {len(flagged) - 20} more")

            if args.anomaly_update:
                update_history_from_result(result, history)
                history.save()

            if args.fail_on_anomaly and report.anomalies_found > 0:
                anomaly_exit = 1
        except AnomalyError as e:
            print(f"error: {e}", file=sys.stderr)
            return EXIT_ERROR

    if anomaly_exit:
        return anomaly_exit
    if args.fail_on_change and result.has_changes:
        return EXIT_CHANGES_FOUND
    return EXIT_NO_CHANGES


if __name__ == "__main__":
    sys.exit(main())
