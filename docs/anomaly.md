# Anomaly Detection

Flag unusual changes in your data by comparing them against historical
values. Uses classical statistical methods (Z-score or IQR).

## Quick Start

```bash
# Build history from past JSON reports
datasift-diff-anomaly old.csv new.csv --key id \
    --history history.json \
    --build-history runs/*.json \
    --threshold 3.0 \
    --fail-on-anomaly

# Or integrate into the main CLI
datasift-diff old.csv new.csv --key id \
    --anomaly-history history.json \
    --anomaly-threshold 3.5 \
    --anomaly-update \
    --fail-on-anomaly
```

## Detection Methods

### Z-score (default)

- **Score**: `(new_value - mean) / stdev`
- **Pros**: Simple, intuitive.
- **Cons**: Sensitive to outliers in history.

### IQR (robust)

- **Score**: `(new_value - median) / (IQR / 1.349)`
- **Pros**: Robust to skewed distributions and outliers.
- **Cons**: Needs more samples to be meaningful.

## Severity Levels

| |Z| Range | Severity |
|--------|----------|
| < threshold | (not flagged) |
| threshold to 4 | medium |
| 4 to 5 | high |
| ≥ 5 | critical |

## Python API

```python
from datasift_diff.anomaly import (
    AnomalyDetector,
    HistoryStore,
    update_history_from_result,
)
from datasift_diff import diff

result = diff("old.csv", "new.csv", key="id")

history = HistoryStore("history.json")
detector = AnomalyDetector(threshold=3.0, method="zscore")
report = detector.detect(result, history)

print(report.summary())
for score in report.scores:
    if score.is_anomaly:
        print(f"{score.key} {score.field}: "
              f"{score.old_value} -> {score.new_value} "
              f"(z={score.z_score:.2f}, severity={score.severity})")

update_history_from_result(result, history)
history.save()
```

## History File Format

```json
{
  "id=1": {
    "score": [10.0, 10.1, 9.9, 10.2, 9.8],
    "age": [30.0, 31.0, 30.5]
  },
  "id=2": {
    "score": [5.5, 5.4, 5.6]
  }
}
```

## Limitations

- Only **numeric** fields are analyzed.
- The detector does not model **seasonality** or **trends**.
- **Cold start**: needs at least `min_history` samples before judging.