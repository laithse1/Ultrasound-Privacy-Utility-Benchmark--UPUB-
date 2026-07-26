"""Generate and evaluate a small, deterministic synthetic DICOM case."""

from dataclasses import dataclass, replace
from pathlib import Path
import random
import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

from us_privbench.synthetic.answer_key import SyntheticAnswerKey, build_answer_key
from us_privbench.synthetic.identity import SyntheticIdentity, generate_identity


@dataclass(frozen=True)
class GeneratedCase:
    source_path: Path
    injected_path: Path
    answer_key: SyntheticAnswerKey
    source_pixels: np.ndarray


def make_source_pixels(seed: int, width: int = 256, height: int = 256) -> np.ndarray:
    """Create a safe synthetic ultrasound-like image with a lesion-shaped region."""
    rng = random.Random(seed)
    yy, xx = np.mgrid[0:height, 0:width]
    base = 18 + 12 * (xx / max(width - 1, 1))
    cx, cy = width * 0.57, height * 0.58
    rx, ry = width * 0.18, height * 0.12
    lesion = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    noise = np.random.default_rng(seed).normal(0, 4, size=(height, width))
    pixels = base + noise + lesion * rng.uniform(55, 85)
    return np.clip(pixels, 0, 255).astype(np.uint8)


def _uid(namespace: str) -> str:
    """Create a reproducible UID under the UUID-derived DICOM root."""
    return f"2.25.{uuid.uuid5(uuid.NAMESPACE_URL, namespace).int}"


def _file_dataset(path: Path, pixels: np.ndarray, identity: SyntheticIdentity, uid_namespace: str) -> FileDataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = _uid(f"{uid_namespace}|sop")
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = _uid(f"{uid_namespace}|study")
    ds.SeriesInstanceUID = _uid(f"{uid_namespace}|series")
    ds.PatientName = identity.patient_name_dicom
    ds.PatientID = identity.patient_id
    ds.PatientBirthDate = identity.birth_date
    ds.StudyDate = identity.study_date
    ds.StudyID = "SYNTH001"
    ds.InstitutionName = identity.institution_name
    ds.Modality = "US"
    ds.ImageType = ["DERIVED", "SECONDARY"]
    ds.Manufacturer = "UPUB-SYNTHETIC"
    ds.Rows, ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = pixels.tobytes()
    ds.save_as(path, enforce_file_format=True)
    return ds


def _draw_overlay(pixels: np.ndarray, identity: SyntheticIdentity, x: int, y: int) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    image = Image.fromarray(pixels, mode="L")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    rows = (identity.patient_name_display, identity.patient_id, identity.study_date)
    boxes = []
    cursor_y = y
    for text in rows:
        left, top, right, bottom = draw.textbbox((x, cursor_y), text, font=font)
        draw.rectangle((left - 2, top - 2, right + 2, bottom + 2), fill=0)
        draw.text((x, cursor_y), text, fill=255, font=font)
        # PIL rectangles include both endpoints; keep one-pixel safety margin so
        # the answer key covers every pixel intentionally touched by rendering.
        boxes.append((left - 2, top - 2, right - left + 6, bottom - top + 6))
        cursor_y += (bottom - top) + 6
    return np.asarray(image, dtype=np.uint8), boxes


def generate_case(output_dir: str | Path, case_id: str, source_id: str, seed: int) -> GeneratedCase:
    """Write a clean source DICOM, PHI-injected DICOM, and exact answer key."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source_path = output / f"{case_id}.source.dcm"
    injected_path = output / f"{case_id}.injected.dcm"
    identity = generate_identity(seed, source_id)
    source_pixels = make_source_pixels(seed)
    source_identity = SyntheticIdentity("SYNTH-SOURCE", "SOURCE^CASE", "SOURCE", "0000000", "19000101", "20250101", "UPUB")
    _file_dataset(source_path, source_pixels, source_identity, f"{case_id}|{source_id}|source")
    injected_pixels, boxes = _draw_overlay(source_pixels, identity, 8, 8)
    _file_dataset(injected_path, injected_pixels, identity, f"{case_id}|{source_id}|injected")
    answer_key = build_answer_key(
        case_id=case_id, source_id=source_id, seed=seed,
        image_width=source_pixels.shape[1], image_height=source_pixels.shape[0], identity=identity,
    )
    answer_key = replace(answer_key, overlays=tuple(
        replace(row, x=box[0], y=box[1], width=box[2], height=box[3])
        for row, box in zip(answer_key.overlays, boxes)
    ))
    return GeneratedCase(source_path, injected_path, answer_key, source_pixels)


def deidentify_case(input_path: str | Path, output_path: str | Path, answer_key: SyntheticAnswerKey) -> None:
    """Apply the transparent baseline: scrub known tags and black out known boxes."""
    ds = pydicom.dcmread(input_path)
    for tag in ("PatientName", "PatientID", "PatientBirthDate", "StudyDate", "InstitutionName"):
        if hasattr(ds, tag):
            setattr(ds, tag, "")
    pixels = np.frombuffer(ds.PixelData, dtype=np.uint8).reshape(ds.Rows, ds.Columns).copy()
    for row in answer_key.overlays:
        pixels[row.y:row.y + row.height, row.x:row.x + row.width] = 0
    ds.PixelData = pixels.tobytes()
    ds.save_as(output_path, enforce_file_format=True)


def evaluate_deidentification(input_path: str | Path, output_path: str | Path, source_pixels: np.ndarray, answer_key: SyntheticAnswerKey) -> dict[str, float | int | bool]:
    """Score header clearing and preservation outside the known PHI boxes."""
    original = pydicom.dcmread(input_path)
    processed = pydicom.dcmread(output_path)
    residual_fields = sum(bool(getattr(processed, tag, "")) for tag in ("PatientName", "PatientID", "PatientBirthDate", "StudyDate", "InstitutionName"))
    output_pixels = np.frombuffer(processed.PixelData, dtype=np.uint8).reshape(processed.Rows, processed.Columns)
    protected = np.zeros_like(source_pixels, dtype=bool)
    for row in answer_key.overlays:
        protected[row.y:row.y + row.height, row.x:row.x + row.width] = True
    return {
        "header_residual_count": residual_fields,
        "header_clean": residual_fields == 0,
        "clinical_pixels_preserved_outside_phi": bool(np.array_equal(output_pixels[~protected], source_pixels[~protected])),
        "input_pixel_checksum": int(np.frombuffer(original.PixelData, dtype=np.uint8).sum()),
        "output_pixel_checksum": int(output_pixels.sum()),
    }
