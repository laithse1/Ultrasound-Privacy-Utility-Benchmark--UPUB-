"""Summarize the controlled privacy variation suite by rendering condition."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for row in payload["results"]:
        groups[row["contrast"]].append(row)
    summary = {
        "suite": payload["suite"],
        "cases": payload["cases"],
        "by_contrast": {
            str(contrast): {
                "cases": len(rows),
                "mean_precision": sum(row["precision"] for row in rows) / len(rows),
                "mean_recall": sum(row["recall"] for row in rows) / len(rows),
            }
            for contrast, rows in sorted(groups.items())
        },
    }
    text = json.dumps(summary, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
