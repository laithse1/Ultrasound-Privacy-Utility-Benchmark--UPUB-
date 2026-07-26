"""Run an expanded controlled pixel-PHI robustness and negative-control suite."""

import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from us_privbench.synthetic.detection import detect_bright_components, evaluate_regions


def render(label: str, *, contrast: int, x: int, y: int, scale: int, blur: float, jpeg_quality: int | None) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    pixels = np.full((256, 256), 24, dtype=np.uint8)
    image = Image.fromarray(pixels, mode="L")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=scale)
    truth = []
    for index, text in enumerate(label.split("|")):
        top = y + index * (scale + 5)
        left, upper, right, lower = draw.textbbox((x, top), text, font=font)
        draw.text((x, top), text, fill=contrast, font=font)
        truth.append((left, upper, right - left + 1, lower - upper + 1))
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur))
    if jpeg_quality is not None:
        buffer = io.BytesIO()
        image.convert("L").save(buffer, format="JPEG", quality=jpeg_quality)
        buffer.seek(0)
        image = Image.open(buffer).convert("L")
    return np.asarray(image), truth


def run_case(*, case_type: str, label: str, truth_enabled: bool, contrast: int, x: int, y: int, scale: int, blur: float, jpeg_quality: int | None, threshold: int, ocr: bool) -> dict:
    pixels, truth = render(label, contrast=contrast, x=x, y=y, scale=scale, blur=blur, jpeg_quality=jpeg_quality)
    result = evaluate_regions(detect_bright_components(pixels, threshold=threshold), truth if truth_enabled else [])
    result.update({
        "case_type": case_type,
        "contrast": contrast,
        "x": x,
        "y": y,
        "scale": scale,
        "blur": blur,
        "jpeg_quality": jpeg_quality,
        "threshold": threshold,
    })
    if ocr:
        from us_privbench.synthetic.detection import detect_ocr_regions

        ocr_result = evaluate_regions(detect_ocr_regions(pixels), truth if truth_enabled else [])
        result.update({f"ocr_{key}": value for key, value in ocr_result.items()})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/privacy-robustness-suite/metrics.json"))
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    rows = []
    for contrast in (128, 160, 180, 220, 255):
        for x, y in ((4, 4), (32, 32)):
            for scale in (8, 12):
                for blur, quality in ((0.0, None), (0.8, 70)):
                    rows.append(run_case(case_type="positive_phi", label="SYNTH PATIENT|UPUB-0007|20250101", truth_enabled=True, contrast=contrast, x=x, y=y, scale=scale, blur=blur, jpeg_quality=quality, threshold=180, ocr=args.ocr))
    for label in ("ULTRASOUND|LEFT|DEPTH 5CM", "B-MODE|GAIN 60|FREQ 7MHZ"):
        for x, y in ((4, 4), (32, 32)):
            for scale in (8, 12):
                rows.append(run_case(case_type="negative_control", label=label, truth_enabled=False, contrast=255, x=x, y=y, scale=scale, blur=0.0, jpeg_quality=None, threshold=180, ocr=args.ocr))
    result = {
        "schema": "upub-privacy-robustness-v1",
        "suite": "rendered-text-variation-with-negative-controls",
        "cases": len(rows),
        "detector": "connected bright components, ROI=(0,0,160,80), threshold=180, min_area=2",
        "ocr_baseline": "full suite" if args.ocr else "canonical case measured separately in artifacts/ocr-smoke/metrics.json; full variation OCR was not run",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"suite": result["suite"], "cases": len(rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
