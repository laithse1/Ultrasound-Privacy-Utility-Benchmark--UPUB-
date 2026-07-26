"""Aggregate validation/test metrics from a runner crossval-results.json."""

import argparse
import json
import statistics
from pathlib import Path


def summarize(rows: list[dict]) -> dict:
    validation = [float(row["validation_dice"]) for row in rows]
    test = [float(row["test_dice"]) for row in rows]
    t_value = 2.776 if len(rows) == 5 else 0.0

    def summary(values: list[float]) -> dict:
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        margin = t_value * std / (len(values) ** 0.5) if len(values) > 1 else 0.0
        return {"mean": mean, "std": std, "ci95": [mean - margin, mean + margin]}

    validation_summary = summary(validation)
    test_summary = summary(test)
    return {
        "architecture": rows[0].get("architecture"),
        "seed": rows[0].get("seed"),
        "folds": [{"fold": row["validation_fold"], "test_fold": row["test_fold"], "validation_dice": row["validation_dice"], "test_dice": row["test_dice"]} for row in rows],
        "validation_mean": validation_summary["mean"],
        "validation_std": validation_summary["std"],
        "validation_ci95": validation_summary["ci95"],
        "test_mean": test_summary["mean"],
        "test_std": test_summary["std"],
        "test_ci95": test_summary["ci95"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(json.loads(args.results.read_text(encoding="utf-8")))
    output = args.output or args.results.with_name("aggregate-results.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
