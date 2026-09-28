"""CLI for anomaly detection on diff reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datasift_diff.anomaly import (
    AnomalyDetector,
    AnomalyError,
    HistoryStore,
    load_history_from_runs,
    update_history_from_result,
)
from datasift_diff.core import DiffError, diff
from datasift_diff.io import DataLoadError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datasift-diff-anomaly",
        description="Detect anomalous changes across a history of diff runs.",
        epilog=(
            "Examples:\n"
            "  datasift-diff-anomaly old.csv new.csv --key id --history history.json\n"
            "  datasift-diff-anomaly old.csv new.csv --key id \\\n"
            "      --build-history runs/*.json --history history.json \\\n"
            "      --threshold 3.5 --method iqr --format json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("old", help="Old dataset.")
    parser.add_argument("new", help="New dataset.")
    parser.add_argument("--key", "-k", required=True, action="append",
                        help="Key field(s). Repeat or comma-separate.")
    parser.add_argument("--ignore", "-i", default="",
                        help="Comma-separated fields to ignore.")
    parser.add_argument("--history", required=True,
                        help="Path to the history JSON file.")
    parser.add_argument("--build-history", nargs="*", default=[],
                        help="Prior JSON reports to seed the history from.")
    parser.add_argument("--threshold", "-t", type=float, default=3.0,
                        help="Z-score threshold (default: 3.0).")
    parser.add_argument("--method", choices=["zscore", "iqr"], default="zscore",
                        help="Detection method (default: zscore).")
    parser.add_argument("--min-history", type=int, default=5,
                        help="Minimum history samples (default: 5).")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text",
                        help="Output format (default: text).")
    parser.add_argument("--update-history", action="store_true",
                        help="Record new values into the history after analysis.")
    parser.add_argument("--fail-on-anomaly", action="store_true",
                        help="Exit 1 if any anomalies are found.")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress output.")
    return parser


def _collect_keys(args_keys: list[str]) -> list[str]:
    out: list[str] = []
    for raw in args_keys:
        for part in raw.split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _render_text(report) -> str:
    lines = ["=" * 60, "Anomaly Report", "=" * 60, report.summary(), ""]

    if not report.scores:
        lines.append("No numeric changes with sufficient history.")
        return "\n".join(lines)

    flagged = [s for s in report.scores if s.is_anomaly]
    if not flagged:
        lines.append("No anomalies detected.")
        return "\n".join(lines)

    lines.append(f"Flagged changes ({len(flagged)}):")
    for s in sorted(flagged, key=lambda x: abs(x.z_score), reverse=True):
        lines.append(
            f"  [{s.severity.upper():8s}] {s.key}  {s.field}: "
            f"{s.old_value} -> {s.new_value}  (z={s.z_score:+.2f})"
        )
    return "\n".join(lines)


def _render_json(report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    history_path = Path(args.history)

    if args.build_history:
        store = load_history_from_runs(args.build_history)
        if history_path.exists():
            existing = HistoryStore(history_path)
            for key, fields in store.all_histories().items():
                for field, values in fields.items():
                    for v in values:
                        existing.record(key, field, v)
            store = existing
        final = HistoryStore(history_path)
        for key, fields in store.all_histories().items():
            for field, values in fields.items():
                for v in values:
                    final.record(key, field, v)
        final.save()
        history = final
    else:
        history = HistoryStore(history_path)

    try:
        keys = _collect_keys(args.key)
        ignore = [f.strip() for f in args.ignore.split(",") if f.strip()]
        result = diff(args.old, args.new, key=keys, ignore_fields=ignore)
    except (DataLoadError, DiffError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        detector = AnomalyDetector(
            threshold=args.threshold,
            method=args.method,
            min_history=args.min_history,
        )
        report = detector.detect(result, history)
    except AnomalyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        if args.format == "json":
            print(_render_json(report))
        else:
            print(_render_text(report))

    if args.update_history:
        update_history_from_result(result, history)
        history.save()

    if args.fail_on_anomaly and report.anomalies_found > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
