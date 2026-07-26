"""Create a UPUB manifest from the official BUS-BRA release layout."""

import argparse
import csv
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BUS-BRA into a patient-disjoint UPUB manifest")
    parser.add_argument("release_root", type=Path, help="directory containing Images, Masks, and CSV files")
    parser.add_argument("--output", type=Path, default=Path("artifacts/busbra-manifest.json"))
    parser.add_argument("--validation-fold", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--test-fold", type=int, default=2, choices=range(1, 6))
    parser.add_argument("--version", default="zenodo-8231412-v1.0")
    args = parser.parse_args()
    if args.validation_fold == args.test_fold:
        raise ValueError("validation and test folds must be different")
    root = args.release_root
    with (root / "bus_data.csv").open(newline="", encoding="utf-8-sig") as stream:
        metadata = {row["ID"]: row for row in csv.DictReader(stream)}
    with (root / "5-fold-cv.csv").open(newline="", encoding="utf-8-sig") as stream:
        folds = {row["ID"]: row for row in csv.DictReader(stream)}
    records = []
    for case_id, row in sorted(metadata.items()):
        if case_id not in folds:
            raise ValueError(f"missing 5-fold metadata for {case_id}")
        fold = int(folds[case_id]["kFold"])
        split = "validation" if fold == args.validation_fold else "test" if fold == args.test_fold else "train"
        image = (root / "Images" / f"{case_id}.png").resolve()
        mask = (root / "Masks" / f"mask_{case_id.removeprefix('bus_')}.png").resolve()
        if not image.exists() or not mask.exists():
            raise FileNotFoundError(f"missing BUS-BRA image or mask for {case_id}")
        records.append(CaseRecord(
            case_id=case_id,
            patient_group=f"case-{row['Case']}",
            split=split,
            image_uri=str(image),
            mask_uri=str(mask),
            dataset_name="BUS-BRA",
            dataset_version=args.version,
        ))
    write_manifest(records, args.output)
    print(f"wrote {len(records)} BUS-BRA records: validation_fold={args.validation_fold} test_fold={args.test_fold} output={args.output}")


if __name__ == "__main__":
    main()
