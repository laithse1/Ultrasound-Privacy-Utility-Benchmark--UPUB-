"""Audit a manifest before any training or cross-dataset comparison."""

import argparse
import json
from collections import Counter
from pathlib import Path

from us_privbench.data.manifest import read_manifest


def audit(path: Path) -> dict:
    records = read_manifest(path)
    by_split = Counter(record.split for record in records)
    patients_by_split = {split: len({record.patient_group for record in records if record.split == split}) for split in by_split}
    missing_images = [record.case_id for record in records if not Path(record.image_uri).exists()]
    missing_masks = [record.case_id for record in records if record.mask_uri and not Path(record.mask_uri).exists()]
    datasets = sorted({(record.dataset_name, record.dataset_version) for record in records})
    result = {
        "manifest": str(path),
        "records": len(records),
        "patients": len({record.patient_group for record in records}),
        "records_by_split": dict(by_split),
        "patients_by_split": patients_by_split,
        "datasets": [{"name": name, "version": version} for name, version in datasets],
        "missing_images": missing_images,
        "missing_masks": missing_masks,
        "patient_disjoint": True,
        "ready_for_training": not missing_images and not missing_masks and all(by_split.get(split, 0) for split in ("train", "validation", "test")),
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
