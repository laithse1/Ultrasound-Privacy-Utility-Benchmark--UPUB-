"""Aggregate independent experiment JSON results with bootstrap intervals."""

import argparse
import json
from pathlib import Path

import numpy as np


def bootstrap_interval(values: list[float], seed: int = 7, samples: int = 5000) -> list[float]:
    if len(values) < 2:
        return [values[0], values[0]] if values else [0.0, 0.0]
    rng = np.random.default_rng(seed)
    resampled = rng.choice(np.asarray(values, dtype=float), size=(samples, len(values)), replace=True).mean(axis=1)
    return [float(np.quantile(resampled, 0.025)), float(np.quantile(resampled, 0.975))]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--field", default="test_dice")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
    values = [float(row[args.field]) for row in rows]
    result = {
        "field": args.field,
        "runs": len(values),
        "values": values,
        "mean": float(np.mean(values)) if values else 0.0,
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "bootstrap_ci95": bootstrap_interval(values),
    }
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
