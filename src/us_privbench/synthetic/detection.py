"""Pixel-PHI detectors and evaluation helpers.

The connected-component detector is deterministic and dependency-free but is
not OCR. The optional Tesseract adapter is explicit so engine versions and
language packs can be pinned in a reproducible experiment.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CandidateRegion:
    x: int
    y: int
    width: int
    height: int
    score: float


def detect_bright_components(
    pixels: np.ndarray,
    *,
    roi: tuple[int, int, int, int] = (0, 0, 160, 80),
    threshold: int = 180,
    min_area: int = 2,
) -> list[CandidateRegion]:
    """Return connected bright components in a restricted banner region."""

    x0, y0, width, height = roi
    crop = pixels[y0:y0 + height, x0:x0 + width]
    active = crop >= threshold
    visited = np.zeros_like(active, dtype=bool)
    regions: list[CandidateRegion] = []
    for row, col in zip(*np.where(active)):
        if visited[row, col]:
            continue
        stack = [(int(row), int(col))]
        visited[row, col] = True
        points: list[tuple[int, int]] = []
        while stack:
            cy, cx = stack.pop()
            points.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < active.shape[0] and 0 <= nx < active.shape[1] and active[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((ny, nx))
        if len(points) >= min_area:
            ys = [point[0] for point in points]
            xs = [point[1] for point in points]
            regions.append(CandidateRegion(
                x=x0 + min(xs), y=y0 + min(ys),
                width=max(xs) - min(xs) + 1, height=max(ys) - min(ys) + 1,
                score=float(len(points)),
            ))
    return regions


def region_recall(candidates: list[CandidateRegion], truth: list[tuple[int, int, int, int]], iou_threshold: float = 0.1) -> float:
    """Compute recall of candidate boxes against truth boxes."""
    if not truth:
        return 1.0
    matched = sum(any(_iou(candidate, expected) >= iou_threshold for candidate in candidates) for expected in truth)
    return matched / len(truth)


def region_precision(candidates: list[CandidateRegion], truth: list[tuple[int, int, int, int]], iou_threshold: float = 0.1) -> float:
    """Compute candidate-level precision against expected PHI regions."""
    if not candidates:
        return 1.0 if not truth else 0.0
    matched = sum(any(_iou(candidate, expected) >= iou_threshold for expected in truth) for candidate in candidates)
    return matched / len(candidates)


def evaluate_regions(candidates: list[CandidateRegion], truth: list[tuple[int, int, int, int]], iou_threshold: float = 0.1) -> dict[str, float | int]:
    """Return auditable region precision/recall counts."""
    return {
        "candidate_count": len(candidates),
        "truth_count": len(truth),
        "precision": region_precision(candidates, truth, iou_threshold),
        "recall": region_recall(candidates, truth, iou_threshold),
        "iou_threshold": iou_threshold,
    }


def detect_ocr_regions(pixels: np.ndarray, *, roi: tuple[int, int, int, int] = (0, 0, 160, 80), min_confidence: float = 0.0) -> list[CandidateRegion]:
    """Detect text boxes with optional Tesseract; raise a setup error if absent."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install the optional 'ocr' extra and a pinned Tesseract binary") from exc
    x0, y0, width, height = roi
    data = pytesseract.image_to_data(Image.fromarray(pixels[y0:y0 + height, x0:x0 + width]), output_type=pytesseract.Output.DICT)
    regions = []
    for x, y, box_width, box_height, confidence, text in zip(data["left"], data["top"], data["width"], data["height"], data["conf"], data["text"]):
        try:
            score = float(confidence)
        except (TypeError, ValueError):
            continue
        if text.strip() and score >= min_confidence and box_width > 0 and box_height > 0:
            regions.append(CandidateRegion(x0 + int(x), y0 + int(y), int(box_width), int(box_height), score))
    return regions


def _iou(candidate: CandidateRegion, expected: tuple[int, int, int, int]) -> float:
    ex, ey, ew, eh = expected
    ax1, ay1 = max(candidate.x, ex), max(candidate.y, ey)
    ax2, ay2 = min(candidate.x + candidate.width, ex + ew), min(candidate.y + candidate.height, ey + eh)
    intersection = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    union = candidate.width * candidate.height + ew * eh - intersection
    return intersection / union if union else 0.0
