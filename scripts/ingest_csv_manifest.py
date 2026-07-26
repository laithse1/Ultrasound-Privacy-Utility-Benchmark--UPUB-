"""Convert a dataset CSV into the UPUB manifest format.

The explicit column arguments make dataset ingestion auditable and avoid
silently guessing which identifier is a patient or which partition is test.
"""

import argparse
import csv
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a UPUB manifest from a dataset CSV")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-column", required=True)
    parser.add_argument("--mask-column", required=True)
    parser.add_argument("--patient-column", required=True)
    parser.add_argument("--split-column", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()
    with args.csv_path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = (args.image_column, args.mask_column, args.patient_column, args.split_column)
    missing = [column for column in required if not rows or column not in rows[0]]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    records = []
    for index, row in enumerate(rows):
        split = row[args.split_column].strip().lower()
        split = {"val": "validation", "dev": "validation"}.get(split, split)
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"unsupported split '{split}' on CSV row {index + 2}")
        image = (args.root / row[args.image_column]).resolve()
        mask = (args.root / row[args.mask_column]).resolve()
        if not image.exists() or not mask.exists():
            raise FileNotFoundError(f"row {index + 2} references missing image or mask: {image}, {mask}")
        records.append(CaseRecord(
            case_id=Path(row[args.image_column]).stem,
            patient_group=row[args.patient_column].strip(),
            split=split,
            image_uri=str(image),
            mask_uri=str(mask),
            dataset_name=args.dataset_name,
            dataset_version=args.dataset_version,
        ))
    write_manifest(records, args.output)
    print(f"wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
