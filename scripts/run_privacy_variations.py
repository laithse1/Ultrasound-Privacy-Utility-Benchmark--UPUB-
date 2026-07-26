"""Run a controlled variation suite for the transparent pixel detector."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from us_privbench.synthetic.detection import detect_bright_components, evaluate_regions


def case(contrast: int, x: int, y: int, scale: int) -> dict:
    pixels = np.full((256, 256), 24, dtype=np.uint8)
    image = Image.fromarray(pixels, mode="L")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=scale)
    truth = []
    for index, text in enumerate(("SYNTH PATIENT", "UPUB-0007", "20250101")):
        top = y + index * (scale + 5)
        left, upper, right, lower = draw.textbbox((x, top), text, font=font)
        draw.text((x, top), text, fill=contrast, font=font)
        truth.append((left, upper, right - left + 1, lower - upper + 1))
    result = evaluate_regions(detect_bright_components(np.asarray(image), threshold=180), truth)
    result.update({"contrast": contrast, "x": x, "y": y, "scale": scale})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/privacy-variation-suite/metrics.json"))
    args = parser.parse_args()
    rows = [case(contrast, x, y, scale) for contrast in (128, 180, 220, 255) for x in (4, 32) for y in (4, 32) for scale in (8, 12)]
    result = {"suite": "controlled-rendered-text-v1", "cases": len(rows), "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"suite": result["suite"], "cases": result["cases"], "output": str(args.output)}, indent=2))
