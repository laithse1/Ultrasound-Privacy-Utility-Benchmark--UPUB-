"""Versioned case manifests with patient-grouped split validation."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    patient_group: str
    split: str
    image_uri: str
    mask_uri: str | None = None
    dataset_name: str = "unknown"
    dataset_version: str = "unknown"

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def validate_patient_disjoint(records: list[CaseRecord]) -> None:
    """Raise if any patient group occurs in more than one split."""
    groups: dict[str, set[str]] = {}
    for record in records:
        groups.setdefault(record.patient_group, set()).add(record.split)
    leaked = {group: splits for group, splits in groups.items() if len(splits) > 1}
    if leaked:
        raise ValueError(f"patient leakage across splits: {leaked}")


def write_manifest(records: list[CaseRecord], path: str | Path) -> None:
    validate_patient_disjoint(records)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps([record.as_dict() for record in records], indent=2), encoding="utf-8")


def read_manifest(path: str | Path) -> list[CaseRecord]:
    records = [CaseRecord(**item) for item in json.loads(Path(path).read_text(encoding="utf-8"))]
    validate_patient_disjoint(records)
    return records
