"""Machine-readable truth for synthetic burned-in PHI.

The answer key is generated from the exact values used by the renderer. That
prevents a later evaluator from trying to infer what the generator intended.
"""

from dataclasses import asdict, dataclass

from us_privbench.synthetic.identity import SyntheticIdentity


@dataclass(frozen=True)
class PixelOverlayTruth:
    phi_category: str
    rendered_text: str
    phi_value: str
    dicom_tag: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SyntheticAnswerKey:
    case_id: str
    source_id: str
    seed: int
    image_width: int
    image_height: int
    identity: SyntheticIdentity
    overlays: tuple[PixelOverlayTruth, ...]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["overlays"] = [asdict(overlay) for overlay in self.overlays]
        return result


def build_answer_key(
    *,
    case_id: str,
    source_id: str,
    seed: int,
    image_width: int,
    image_height: int,
    identity: SyntheticIdentity,
    x: int = 8,
    y: int = 8,
    line_height: int = 18,
) -> SyntheticAnswerKey:
    """Build truth rows for the values that a pixel renderer will draw."""

    lines = (
        ("patient_name", identity.patient_name_display, "PatientName"),
        ("patient_id", identity.patient_id, "PatientID"),
        ("study_date", identity.study_date, "StudyDate"),
    )
    overlays = tuple(
        PixelOverlayTruth(
            phi_category=category,
            rendered_text=value,
            phi_value=value,
            dicom_tag=tag,
            x=x,
            y=y + index * line_height,
            width=0,
            height=line_height,
        )
        for index, (category, value, tag) in enumerate(lines)
    )
    return SyntheticAnswerKey(
        case_id=case_id,
        source_id=source_id,
        seed=seed,
        image_width=image_width,
        image_height=image_height,
        identity=identity,
        overlays=overlays,
    )
