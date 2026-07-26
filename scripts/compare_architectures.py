"""Run a bounded architecture comparison under the same manifest contract."""

import argparse
import json
from pathlib import Path

from us_privbench.data.manifest import read_manifest
from us_privbench.experiment.provenance import write_provenance
from us_privbench.segmentation.monai_train import train_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/architecture-comparison-seeded"))
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--image-size", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit-train", type=int, default=100)
    parser.add_argument("--limit-validation", type=int, default=50)
    parser.add_argument("--limit-test", type=int, default=50)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    records = read_manifest(args.manifest)
    results = []
    for architecture in ("unet", "attention_unet", "aau_net"):
        result = train_manifest(
            records,
            output_dir=args.output / architecture,
            epochs=args.epochs,
            image_size=args.image_size,
            batch_size=args.batch_size,
            limit_train=args.limit_train,
            limit_validation=args.limit_validation,
            limit_test=args.limit_test,
            architecture=architecture,
            seed=args.seed,
        )
        results.append(result)
        write_provenance(
            args.output / architecture,
            manifest=args.manifest,
            config={
                "mode": "architecture_comparison",
                "architecture": architecture,
                "epochs": args.epochs,
                "image_size": args.image_size,
                "batch_size": args.batch_size,
                "limit_train": args.limit_train,
                "limit_validation": args.limit_validation,
                "limit_test": args.limit_test,
                "seed": args.seed,
            },
        )
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "results.json"
    destination.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
