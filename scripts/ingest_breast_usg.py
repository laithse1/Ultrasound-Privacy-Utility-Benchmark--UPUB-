"""Ingest the official Breast-Lesions-USG/BrEaST package into UPUB."""

import argparse
import hashlib
from pathlib import Path

from us_privbench.data.manifest import CaseRecord, write_manifest


def stable_split(case_id: str, test_fraction: float, validation_fraction: float) -> str:
    bucket = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < test_fraction:
        return "test"
    if bucket < test_fraction + validation_fraction:
        return "validation"
    return "train"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest BrEaST/Breast-Lesions-USG")
    parser.add_argument("root", type=Path, help="directory containing the XLSX and images/masks folder")
    parser.add_argument("--clinical-xlsx", type=Path, required=True)
    parser.add_argument("--images-folder", type=Path, default=Path("BrEaST-Lesions_USG-images_and_masks"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/breast-lesions-usg-manifest.json"))
    parser.add_argument("--version", default="TCIA-10.7937-9WKK-Q141-v1")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args()
    if not args.root.exists():
        raise FileNotFoundError(
            f"BrEaST root does not exist: {args.root}. Download and extract the TCIA package first."
        )
    clinical_xlsx = args.clinical_xlsx
    if not clinical_xlsx.is_absolute():
        candidate = args.root / clinical_xlsx
        if candidate.exists():
            clinical_xlsx = candidate
    if not clinical_xlsx.exists():
        raise FileNotFoundError(
            f"BrEaST clinical XLSX not found: {clinical_xlsx}. "
            "Expected the TCIA XLSX filename from the downloaded package."
        )
    images_folder = args.root / args.images_folder
    if not images_folder.exists():
        raise FileNotFoundError(
            f"BrEaST image/mask folder not found: {images_folder}. "
            "Expected BrEaST-Lesions_USG-images_and_masks/."
        )
    if args.test_fraction + args.validation_fraction >= 1:
        raise ValueError("test and validation fractions must leave training cases")

    import pandas as pd

    table = pd.read_excel(clinical_xlsx, sheet_name=0)
    records = []
    skipped = 0
    for row in table.to_dict(orient="records"):
        case_id_value = row.get("Case_ID", row.get("CaseID"))
        if case_id_value is None:
            raise KeyError("BrEaST clinical table must contain Case_ID or CaseID")
        case_id = str(case_id_value)
        mask_name = row.get("Mask_tumor_filename")
        if not isinstance(mask_name, str) or not mask_name.strip():
            skipped += 1
            continue
        image = (images_folder / str(row["Image_filename"])).resolve()
        mask = (images_folder / mask_name.split("&")[0]).resolve()
        if not image.exists() or not mask.exists():
            raise FileNotFoundError(f"missing BrEaST image or tumor mask for {case_id}: {image} / {mask}")
        records.append(CaseRecord(
            case_id=f"breast-usg-{case_id}",
            patient_group=f"breast-usg-patient-{case_id}",
            split=stable_split(case_id, args.test_fraction, args.validation_fraction),
            image_uri=str(image),
            mask_uri=str(mask),
            dataset_name="Breast-Lesions-USG",
            dataset_version=args.version,
        ))
    write_manifest(records, args.output)
    print(f"wrote {len(records)} masked BrEaST records; skipped_unmasked={skipped}; output={args.output}")


if __name__ == "__main__":
    main()
