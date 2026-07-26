import argparse
from pathlib import Path

from PIL import Image

from us_privbench.data.manifest import CaseRecord, write_manifest
from us_privbench.segmentation.baseline import lesion_mask
from us_privbench.synthetic.dicom import make_source_pixels


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local image/mask demo dataset")
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo-image-dataset"))
    args = parser.parse_args()
    records = []
    for index, split in enumerate(("train", "train", "train", "validation", "validation", "test")):
        case_id = f"demo-{split}-{index:03d}"
        image_path = args.output / "images" / f"{case_id}.png"
        mask_path = args.output / "masks" / f"{case_id}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        pixels = make_source_pixels(100 + index, width=64, height=64)
        mask = lesion_mask(64, 64).astype("uint8") * 255
        Image.fromarray(pixels).save(image_path)
        Image.fromarray(mask).save(mask_path)
        records.append(CaseRecord(case_id, f"patient-{index:03d}", split, str(image_path), str(mask_path), "upub-demo-images", "0.1"))
    manifest_path = args.output / "manifest.json"
    write_manifest(records, manifest_path)
    print(f"wrote {len(records)} image/mask cases to {manifest_path}")


if __name__ == "__main__":
    main()
