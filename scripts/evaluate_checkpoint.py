"""Evaluate a frozen segmentation checkpoint on another manifest.

This is a zero-shot transfer evaluation: no target-dataset images are used for
training or checkpoint selection.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from us_privbench.data.image_dataset import ManifestImageDataset
from us_privbench.data.manifest import read_manifest
from us_privbench.segmentation.baseline import binary_metrics
from us_privbench.segmentation.monai_backend import build_model


def bootstrap_ci(values: list[float], *, seed: int = 7, samples: int = 10000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [values[0], values[0]]
    rng = np.random.default_rng(seed)
    draws = rng.choice(np.asarray(values, dtype=float), (samples, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/transfer-evaluation.json"))
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit-test", type=int)
    parser.add_argument("--architecture", choices=("unet", "attention_unet", "aau_net"), default="unet")
    parser.add_argument("--source-dataset", default="unspecified training source")
    parser.add_argument("--per-case-output", type=Path)
    args = parser.parse_args()

    import torch

    records = [record for record in read_manifest(args.manifest) if record.split == "test"]
    if args.limit_test is not None:
        records = records[: args.limit_test]
    if not records:
        raise ValueError("transfer evaluation requires a non-empty test split")
    model = build_model(architecture=args.architecture)
    state = torch.load(args.checkpoint, map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    scores = []
    per_case = []
    with torch.no_grad():
        dataset = ManifestImageDataset(records, size=args.image_size)
        for index, record in enumerate(records):
            image, mask = dataset[index]
            prediction = (torch.sigmoid(model(image.unsqueeze(0))) >= 0.5).numpy()[0, 0]
            score = binary_metrics(prediction, mask.numpy()[0])
            scores.append(score)
            per_case.append({
                "case_id": record.case_id,
                "patient_group": record.patient_group,
                "split": record.split,
                **score,
            })
    metrics = {f"test_{name}": float(np.mean([score[name] for score in scores])) for name in scores[0]}
    grouped = {}
    for row in per_case:
        grouped.setdefault(row["patient_group"], []).append(row)
    patient_metrics = {}
    for name in scores[0]:
        group_values = [float(np.mean([row[name] for row in rows])) for rows in grouped.values()]
        patient_metrics[name] = {
            "groups": len(group_values),
            "mean": float(np.mean(group_values)) if group_values else 0.0,
            "sample_std": float(np.std(group_values, ddof=1)) if len(group_values) > 1 else 0.0,
            "bootstrap_ci95": bootstrap_ci(group_values),
        }
    result = {
        "mode": "zero_shot_transfer",
        "checkpoint": str(args.checkpoint),
        "source_training_dataset": args.source_dataset,
        "target_manifest": str(args.manifest),
        "target_dataset": records[0].dataset_name,
        "target_version": records[0].dataset_version,
        "architecture": args.architecture,
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "test_cases": len(records),
        "target_patient_group_note": "target release grouping follows its manifest provenance; no target fine-tuning or checkpoint selection was performed",
        "patient_group_metrics": patient_metrics,
        **metrics,
    }
    if args.per_case_output:
        result["per_case_output"] = str(args.per_case_output)
        args.per_case_output.parent.mkdir(parents=True, exist_ok=True)
        args.per_case_output.write_text(json.dumps({"records": per_case}, indent=2), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
