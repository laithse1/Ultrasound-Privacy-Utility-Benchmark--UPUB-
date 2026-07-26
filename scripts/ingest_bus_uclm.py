"""Ingest the official BUS-UCLM folder layout with patient-level splits."""

import argparse
import json
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


DEFAULT_TEST_PATIENTS = {"COPE", "ANFO", "ELCO", "CRCI", "FLKA"}


def build_records(root: Path, version: str, test_patients: set[str] = DEFAULT_TEST_PATIENTS) -> list[CaseRecord]:
    image_dir, mask_dir = root / "images", root / "masks"
    records = []
    patients = sorted({path.stem[:4] for path in image_dir.glob("*.png")})
    validation_patients = set(patients[: max(1, len(patients) // 5)]) - test_patients
    for image in sorted(image_dir.glob("*.png")):
        mask = mask_dir / image.name
        if not mask.exists():
            raise FileNotFoundError(mask)
        patient = image.stem[:4]
        split = "test" if patient in test_patients else "validation" if patient in validation_patients else "train"
        records.append(CaseRecord(
            case_id=image.stem,
            patient_group=f"BUS-UCLM-{patient}",
            split=split,
            image_uri=str(image.resolve()),
            mask_uri=str(mask.resolve()),
            dataset_name="BUS-UCLM",
            dataset_version=version,
        ))
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="BUS-UCLM data folder containing images/ and masks/")
    parser.add_argument("--output", type=Path, default=Path("artifacts/bus-uclm-manifest.json"))
    parser.add_argument("--version", default="mendeley-v3")
    args = parser.parse_args()
    records = build_records(args.root, args.version)
    write_manifest(records, args.output)
    print(json.dumps({"records": len(records), "output": str(args.output)}, indent=2))
