import argparse
import json
from pathlib import Path

import numpy as np
import pydicom

from us_privbench.segmentation.baseline import evaluate_segmentation, lesion_mask
from us_privbench.synthetic.dicom import deidentify_case, generate_case


def _pixels(path: Path) -> np.ndarray:
    return pydicom.dcmread(path).pixel_array


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first UPUB privacy-utility experiment")
    parser.add_argument("--output", type=Path, default=Path("artifacts/utility-experiment"))
    args = parser.parse_args()
    generated = generate_case(args.output, "utility-case", "utility-source-001", 7)
    deidentified_path = args.output / "utility-case.deidentified.dcm"
    deidentify_case(generated.injected_path, deidentified_path, generated.answer_key)
    truth = lesion_mask(*generated.source_pixels.shape)
    result = {
        "clean_source": evaluate_segmentation(generated.source_pixels, truth),
        "phi_injected": evaluate_segmentation(_pixels(generated.injected_path), truth),
        "deidentified": evaluate_segmentation(_pixels(deidentified_path), truth),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "utility-metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
