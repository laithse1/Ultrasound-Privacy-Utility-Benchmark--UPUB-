"""Ingest the BUSI-WHU-Seg public mirror without implying canonical BUSI identity."""

import argparse
import csv
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BUSI-WHU-Seg into a UPUB manifest")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/busi-whu-manifest.json"))
    parser.add_argument("--version", default="huggingface-huangjin520-main")
    args = parser.parse_args()
    records: list[CaseRecord] = []
    for split_dir, split in (("train", "train"), ("validation", "validation"), ("test", "test")):
        metadata = args.root / split_dir / "metadata.csv"
        with metadata.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                image = (args.root / split_dir / row["image_file_name"]).resolve()
                mask = (args.root / split_dir / row["mask_file_name"]).resolve()
                if not image.exists() or not mask.exists():
                    raise FileNotFoundError(f"missing BUSI-WHU pair: {image} / {mask}")
                case_id = f"{split}-{image.stem}"
                records.append(CaseRecord(
                    case_id=case_id,
                    patient_group=f"BUSI-WHU-case-{image.stem}",
                    split=split,
                    image_uri=str(image),
                    mask_uri=str(mask),
                    dataset_name="BUSI-WHU-Seg-mirror",
                    dataset_version=args.version,
                ))
    write_manifest(records, args.output)
    print(f"wrote {len(records)} BUSI-WHU mirror records: output={args.output}")


if __name__ == "__main__":
    main()
