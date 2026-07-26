"""Summarize per-case exports from seed runs with patient-group bootstrap CIs."""

import argparse
import json
from pathlib import Path

import numpy as np


METRICS = ("dice", "iou", "precision", "recall", "specificity")


def bootstrap(values: list[float], seed: int = 7, samples: int = 10000) -> list[float]:
    if len(values) < 2:
        return [values[0], values[0]] if values else [0.0, 0.0]
    rng = np.random.default_rng(seed)
    draws = rng.choice(np.asarray(values, dtype=float), (samples, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarize(path: Path) -> dict:
    rows = json.loads((path / "test-per-case.json").read_text(encoding="utf-8"))["records"]
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["patient_group"], []).append(row)
    metrics = {}
    for metric in METRICS:
        case_values = [float(row[metric]) for row in rows]
        group_values = [float(np.mean([row[metric] for row in group])) for group in groups.values()]
        metrics[metric] = {
            "case_mean": float(np.mean(case_values)),
            "patient_groups": len(group_values),
            "patient_group_mean": float(np.mean(group_values)),
            "patient_group_sample_std": float(np.std(group_values, ddof=1)) if len(group_values) > 1 else 0.0,
            "patient_group_bootstrap_ci95": bootstrap(group_values),
        }
    return {"run": path.name, "test_cases": len(rows), "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--grouping-note", required=True)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = {
        "schema": "upub-patient-level-seed-summary-v1",
        "dataset": args.dataset,
        "grouping_note": args.grouping_note,
        "runs": [summarize(path) for path in args.runs],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"dataset": args.dataset, "runs": len(result["runs"]), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
