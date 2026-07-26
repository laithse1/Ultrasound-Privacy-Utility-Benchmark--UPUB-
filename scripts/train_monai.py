"""Entry point for the first learned segmentation experiment."""

import argparse
import json
from pathlib import Path

from us_privbench.data.manifest import read_manifest
from us_privbench.segmentation.monai_backend import build_model
from us_privbench.segmentation.monai_train import train_manifest, train_synthetic_smoke
from us_privbench.experiment.provenance import write_provenance


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the UPUB MONAI segmentation baseline")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--synthetic-smoke", action="store_true")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("artifacts/monai-smoke"))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit-train", type=int)
    parser.add_argument("--limit-validation", type=int)
    parser.add_argument("--limit-test", type=int)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--loss", choices=("dicece", "dicefocal"), default="dicece")
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--architecture", choices=("unet", "attention_unet", "aau_net"), default="unet")
    args = parser.parse_args()
    records = read_manifest(args.manifest)
    if args.synthetic_smoke:
        result = train_synthetic_smoke(output_dir=args.output, epochs=args.epochs)
        write_provenance(args.output, manifest=args.manifest, config={"mode": "synthetic_smoke", "epochs": args.epochs, "seed": args.seed})
        print(json.dumps(result, indent=2))
        return
    if all(Path(record.image_uri).exists() for record in records):
        result = train_manifest(records, output_dir=args.output, epochs=args.epochs, image_size=args.image_size, batch_size=args.batch_size, limit_train=args.limit_train, limit_validation=args.limit_validation, limit_test=args.limit_test, loss_name=args.loss, augment=not args.no_augment, architecture=args.architecture, seed=args.seed)
        write_provenance(args.output, manifest=args.manifest, config={"mode": "manifest", "architecture": args.architecture, "epochs": args.epochs, "image_size": args.image_size, "batch_size": args.batch_size, "limit_train": args.limit_train, "limit_validation": args.limit_validation, "limit_test": args.limit_test, "seed": args.seed})
        print(json.dumps(result, indent=2))
        return
    model = build_model(architecture=args.architecture)
    counts = {split: sum(record.split == split for record in records) for split in ("train", "validation", "test")}
    print(f"MONAI model ready: {sum(parameter.numel() for parameter in model.parameters()):,} parameters")
    print(f"patient-disjoint records: train={counts['train']} validation={counts['validation']} test={counts['test']}")
    print("image loading and optimizer wiring are the next implementation step")


if __name__ == "__main__":
    main()
