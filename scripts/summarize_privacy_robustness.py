"""Summarize positive and negative-control privacy robustness results."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for row in payload["results"]:
        groups[(row["case_type"], row["contrast"], row["blur"], row["jpeg_quality"])].append(row)
    summary = []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        case_type, contrast, blur, quality = key
        summary.append({
            "case_type": case_type,
            "contrast": contrast,
            "blur": blur,
            "jpeg_quality": quality,
            "cases": len(rows),
            "mean_candidate_count": float(np.mean([row["candidate_count"] for row in rows])),
            "mean_precision": float(np.mean([row["precision"] for row in rows])),
            "mean_recall": float(np.mean([row["recall"] for row in rows])),
        })
        if "ocr_precision" in rows[0]:
            summary[-1].update({
                "mean_ocr_precision": float(np.mean([row["ocr_precision"] for row in rows])),
                "mean_ocr_recall": float(np.mean([row["ocr_recall"] for row in rows])),
            })
    result = {
        "schema": "upub-privacy-robustness-summary-v1",
        "source": str(args.metrics),
        "cases": payload["cases"],
        "groups": summary,
        "interpretation": "Negative controls estimate false-positive exposure. OCR metrics are produced inside the pinned Tesseract container when metrics-ocr.json is used.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"groups": len(summary), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
