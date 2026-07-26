"""Build a normalized publication statistics table from three-seed summaries."""

import argparse
import json
from pathlib import Path

import numpy as np


METRICS = ("test_dice", "test_iou", "test_precision", "test_recall", "test_specificity")


def bootstrap_ci(values: list[float], *, seed: int = 7, samples: int = 10000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [values[0], values[0]]
    rng = np.random.default_rng(seed)
    draws = rng.choice(np.asarray(values, dtype=float), (samples, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarize(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("runs", [])
    # BUS-BRA was produced by the generic aggregator and stores only the
    # primary metric as values; preserve it while marking other metrics absent.
    if isinstance(rows, int):
        field = payload.get("field", "test_dice")
        rows = [{field: value} for value in payload.get("values", [])]
    metrics = {}
    for metric in METRICS:
        values = [float(row[metric]) for row in rows if metric in row]
        metrics[metric] = {
            "values": values,
            "mean": float(np.mean(values)) if values else 0.0,
            "sample_std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "bootstrap_ci95": bootstrap_ci(values),
        }
    return {
        "dataset": payload.get("dataset", path.stem),
        "source_summary": str(path),
        "protocol": payload.get("protocol", {}),
        "runs": len(rows),
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summaries", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema": "upub-final-statistics-v1",
        "datasets": [summarize(path) for path in args.summaries],
        "interpretation": (
            "Intervals are bootstrap intervals over independent training seeds, not "
            "patient-level confidence intervals. Patient-level intervals require "
            "per-case prediction exports and are a separate analysis gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"datasets": len(result["datasets"]), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
