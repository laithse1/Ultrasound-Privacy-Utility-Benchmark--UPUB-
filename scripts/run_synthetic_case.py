import argparse
import json
from pathlib import Path

import numpy as np
import pydicom

from us_privbench.synthetic.dicom import deidentify_case, evaluate_deidentification, generate_case
from us_privbench.synthetic.detection import detect_bright_components, evaluate_regions


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and evaluate one UPUB synthetic case")
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo-case"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ocr", action="store_true", help="also evaluate optional Tesseract OCR regions")
    args = parser.parse_args()
    generated = generate_case(args.output, "demo-case", "demo-source-001", args.seed)
    deidentified = args.output / "demo-case.deidentified.dcm"
    deidentify_case(generated.injected_path, deidentified, generated.answer_key)
    result = evaluate_deidentification(generated.injected_path, deidentified, generated.source_pixels, generated.answer_key)
    injected_pixels = np.asarray(pydicom.dcmread(generated.injected_path).pixel_array, dtype=np.uint8)
    truth_boxes = [(row.x, row.y, row.width, row.height) for row in generated.answer_key.overlays]
    result["pixel_detector_components"] = evaluate_regions(
        detect_bright_components(injected_pixels), truth_boxes
    )
    result["pixel_detector_components"]["threat_model"] = "bright-rendered-text-in-known-banner"
    if args.ocr:
        from us_privbench.synthetic.detection import detect_ocr_regions

        result["pixel_detector_ocr"] = evaluate_regions(
            detect_ocr_regions(injected_pixels), truth_boxes
        )
        result["pixel_detector_ocr"]["engine"] = "tesseract"
    (args.output / "answer-key.json").write_text(json.dumps(generated.answer_key.as_dict(), indent=2), encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
