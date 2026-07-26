"""Run the pre-registered locked BUS-BRA architecture comparison."""

import argparse
import json
from pathlib import Path

from us_privbench.data.manifest import write_manifest
from us_privbench.experiment.provenance import write_provenance
from us_privbench.segmentation.monai_train import train_manifest
from run_busbra_cv import build_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_root", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/locked-busbra-comparison.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/locked-busbra-comparison"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    records = build_records(args.release_root, config["validation_fold"], config["test_fold"], config["dataset_version"])
    manifest = args.output / "locked-manifest.json"
    write_manifest(records, manifest)
    results = []
    for architecture in config["models"]:
        result = train_manifest(
            records,
            output_dir=args.output / architecture,
            epochs=config["epochs"],
            image_size=config["image_size"],
            batch_size=config["batch_size"],
            limit_train=config["limit_train"],
            limit_validation=config["limit_validation"],
            limit_test=config["limit_test"],
            loss_name=config["loss"],
            augment=config["augmentation"],
            architecture=architecture,
            seed=config["seed"],
        )
        results.append(result)
        write_provenance(args.output / architecture, manifest=manifest, config={**config, "architecture": architecture})
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "results.json"
    destination.write_text(json.dumps({"config": config, "results": results}, indent=2), encoding="utf-8")
    print(json.dumps({"config": config, "results": results}, indent=2))


if __name__ == "__main__":
    main()
