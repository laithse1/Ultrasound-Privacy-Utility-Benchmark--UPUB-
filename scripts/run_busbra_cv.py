"""Run fold-level BUS-BRA experiments with patient-grouped splits."""

import argparse
import csv
import json
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest
from us_privbench.segmentation.monai_train import train_manifest
from us_privbench.experiment.provenance import write_provenance


def build_records(root: Path, validation_fold: int, test_fold: int, version: str) -> list[CaseRecord]:
    with (root / "bus_data.csv").open(newline="", encoding="utf-8-sig") as stream:
        metadata = {row["ID"]: row for row in csv.DictReader(stream)}
    with (root / "5-fold-cv.csv").open(newline="", encoding="utf-8-sig") as stream:
        folds = {row["ID"]: row for row in csv.DictReader(stream)}
    if validation_fold == test_fold:
        raise ValueError("validation and test folds must differ")
    records = []
    for case_id, row in sorted(metadata.items()):
        fold = int(folds[case_id]["kFold"])
        split = "validation" if fold == validation_fold else "test" if fold == test_fold else "train"
        records.append(CaseRecord(
            case_id=case_id,
            patient_group=f"case-{row['Case']}",
            split=split,
            image_uri=str((root / "Images" / f"{case_id}.png").resolve()),
            mask_uri=str((root / "Masks" / f"mask_{case_id.removeprefix('bus_')}.png").resolve()),
            dataset_name="BUS-BRA",
            dataset_version=version,
        ))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BUS-BRA patient-grouped cross-validation")
    parser.add_argument("release_root", type=Path)
    parser.add_argument("--folds", nargs="+", type=int, default=[1])
    parser.add_argument("--test-fold", type=int, default=2)
    parser.add_argument("--rotate-test", action="store_true", help="use the next fold as test for each validation fold")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("artifacts/busbra-cv"))
    parser.add_argument("--loss", choices=("dicece", "dicefocal"), default="dicece")
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--architecture", choices=("unet", "attention_unet", "aau_net"), default="unet")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--limit-train", type=int)
    parser.add_argument("--limit-validation", type=int)
    parser.add_argument("--limit-test", type=int)
    args = parser.parse_args()
    results = []
    for fold in args.folds:
        test_fold = (fold % 5) + 1 if args.rotate_test else args.test_fold
        records = build_records(args.release_root, fold, test_fold, "zenodo-8231412-v1.0")
        manifest = args.output / f"fold-{fold}.json"
        write_manifest(records, manifest)
        result = train_manifest(records, output_dir=args.output / f"fold-{fold}", epochs=args.epochs, image_size=args.image_size, batch_size=args.batch_size, loss_name=args.loss, augment=not args.no_augment, architecture=args.architecture, seed=args.seed, limit_train=args.limit_train, limit_validation=args.limit_validation, limit_test=args.limit_test)
        write_provenance(args.output / f"fold-{fold}", manifest=manifest, config={"mode": "busbra_cross_validation", "architecture": args.architecture, "validation_fold": fold, "test_fold": test_fold, "epochs": args.epochs, "image_size": args.image_size, "batch_size": args.batch_size, "limit_train": args.limit_train, "limit_validation": args.limit_validation, "limit_test": args.limit_test, "loss": args.loss, "augment": not args.no_augment, "seed": args.seed})
        result["validation_fold"] = fold
        result["test_fold"] = test_fold
        results.append(result)
        (args.output / f"fold-{fold}" / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "crossval-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
