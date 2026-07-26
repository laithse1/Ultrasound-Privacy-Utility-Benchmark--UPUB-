"""CPU-safe segmentation baseline used before the MONAI model adapter."""

import numpy as np


def lesion_mask(height: int = 256, width: int = 256) -> np.ndarray:
    """Return the deterministic ground-truth lesion mask for the fixture."""
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width * 0.57, height * 0.58
    rx, ry = width * 0.18, height * 0.12
    return (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1)


def threshold_segment(pixels: np.ndarray, threshold: int = 55) -> np.ndarray:
    """Segment the bright synthetic lesion with a deliberately simple rule."""
    return pixels >= threshold


def dice_score(prediction: np.ndarray, truth: np.ndarray) -> float:
    prediction = prediction.astype(bool)
    truth = truth.astype(bool)
    denominator = prediction.sum() + truth.sum()
    return float(2 * np.logical_and(prediction, truth).sum() / denominator) if denominator else 1.0


def iou_score(prediction: np.ndarray, truth: np.ndarray) -> float:
    prediction = prediction.astype(bool)
    truth = truth.astype(bool)
    union = np.logical_or(prediction, truth).sum()
    return float(np.logical_and(prediction, truth).sum() / union) if union else 1.0


def binary_metrics(prediction: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    """Return overlap and pixel-level confusion metrics for binary masks."""
    prediction = prediction.astype(bool)
    truth = truth.astype(bool)
    tp = int(np.logical_and(prediction, truth).sum())
    fp = int(np.logical_and(prediction, ~truth).sum())
    fn = int(np.logical_and(~prediction, truth).sum())
    tn = int(np.logical_and(~prediction, ~truth).sum())
    return {
        "dice": dice_score(prediction, truth),
        "iou": iou_score(prediction, truth),
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 1.0,
        "specificity": tn / (tn + fp) if tn + fp else 1.0,
    }


def evaluate_segmentation(pixels: np.ndarray, truth: np.ndarray, threshold: int = 55) -> dict[str, float | int]:
    prediction = threshold_segment(pixels, threshold)
    return {
        "threshold": threshold,
        "predicted_pixels": int(prediction.sum()),
        "truth_pixels": int(truth.sum()),
        "dice": dice_score(prediction, truth),
        "iou": iou_score(prediction, truth),
    }
