"""Create a UPUB manifest from the public TN3K repository layout.

TN3K publishes an official train/validation-fold JSON and a held-out test
directory.  The release does not expose patient identifiers in the image
filenames, so this manifest records an image-case proxy group and does not
claim patient-level independence within the trainval partition.
"""

import argparse
import json
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def image_path(directory: Path, index: int) -> Path:
    return (directory / f"{index:04d}.jpg").resolve()


def build_records(root: Path, fold: int, version: str) -> list[CaseRecord]:
    fold_path = root / f"tn3k-trainval-fold{fold}.json"
    fold_data = json.loads(fold_path.read_text(encoding="utf-8"))
    validation = {int(index) for index in fold_data["val"]}
    train = {int(index) for index in fold_data["train"]}
    if train & validation or not train or not validation:
        raise ValueError(f"invalid TN3K fold {fold}")

    records: list[CaseRecord] = []
    for index in sorted(train | validation):
        split = "validation" if index in validation else "train"
        image = image_path(root / "trainval-image", index)
        mask = image_path(root / "trainval-mask", index)
        if not image.exists() or not mask.exists():
            raise FileNotFoundError(f"missing TN3K trainval pair for {index:04d}")
        records.append(CaseRecord(
            case_id=f"trainval-{index:04d}",
            patient_group=f"TN3K-case-trainval-{index:04d}",
            split=split,
            image_uri=str(image),
            mask_uri=str(mask),
            dataset_name="TN3K",
            dataset_version=version,
        ))

    test_images = sorted((root / "test-image").glob("*.jpg"))
    for image in test_images:
        mask = root / "test-mask" / image.name
        if not mask.exists():
            raise FileNotFoundError(f"missing TN3K test mask for {image.name}")
        case_id = f"test-{image.stem}"
        records.append(CaseRecord(
            case_id=case_id,
            patient_group=f"TN3K-case-{case_id}",
            split="test",
            image_uri=str(image.resolve()),
            mask_uri=str(mask.resolve()),
            dataset_name="TN3K",
            dataset_version=version,
        ))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TN3K into a UPUB manifest")
    parser.add_argument("root", type=Path)
    parser.add_argument("--fold", type=int, default=0, choices=range(5))
    parser.add_argument("--output", type=Path, default=Path("artifacts/tn3k-manifest.json"))
    parser.add_argument("--version", default="huggingface-haifan-gong-main")
    args = parser.parse_args()
    records = build_records(args.root, args.fold, args.version)
    write_manifest(records, args.output)
    print(f"wrote {len(records)} TN3K records: fold={args.fold} output={args.output}")


if __name__ == "__main__":
    main()
