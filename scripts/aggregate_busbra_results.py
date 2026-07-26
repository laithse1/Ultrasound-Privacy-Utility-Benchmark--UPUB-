"""Aggregate completed BUS-BRA fold metrics."""

import argparse
import json
from pathlib import Path
import statistics


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate BUS-BRA cross-validation metrics")
    parser.add_argument("results", nargs="+", help="fold=validation_dice,test_dice")
    parser.add_argument("--output", type=Path, default=Path("artifacts/busbra-cv-rotating/aggregate-results.json"))
    args = parser.parse_args()
    rows = []
    for item in args.results:
        fold, scores = item.split("=", 1)
        validation, test = scores.split(",", 1)
        rows.append({"fold": int(fold), "validation_dice": float(validation), "test_dice": float(test)})
    validation_scores = [row["validation_dice"] for row in rows]
    test_scores = [row["test_dice"] for row in rows]
    test_std = statistics.stdev(test_scores) if len(rows) > 1 else 0.0
    validation_std = statistics.stdev(validation_scores) if len(rows) > 1 else 0.0
    test_margin = 2.776 * test_std / (len(rows) ** 0.5) if len(rows) > 1 else 0.0
    validation_margin = 2.776 * validation_std / (len(rows) ** 0.5) if len(rows) > 1 else 0.0
    result = {
        "folds": rows,
        "validation_mean": statistics.mean(validation_scores),
        "validation_std": validation_std,
        "validation_ci95": [statistics.mean(validation_scores) - validation_margin, statistics.mean(validation_scores) + validation_margin],
        "test_mean": statistics.mean(test_scores),
        "test_std": test_std,
        "test_ci95": [statistics.mean(test_scores) - test_margin, statistics.mean(test_scores) + test_margin],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
