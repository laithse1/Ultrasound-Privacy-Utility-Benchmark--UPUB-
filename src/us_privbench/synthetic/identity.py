"""Generate reproducible synthetic identifiers for benchmark fixtures.

This module intentionally does not touch image or DICOM files yet. It establishes
the deterministic truth object that later renderers will consume.
"""

from dataclasses import asdict, dataclass
import hashlib
import random
import uuid


FIRST_NAMES = ("Alex", "Jordan", "Morgan", "Taylor", "Riley", "Casey")
LAST_NAMES = ("Rivera", "Chen", "Patel", "Nguyen", "Morgan", "Haddad")
INSTITUTIONS = ("SYNTH-US-01", "SYNTH-US-02", "SYNTH-US-03")


@dataclass(frozen=True)
class SyntheticIdentity:
    """Synthetic values that can be written to DICOM and pixel overlays."""

    case_uuid: str
    patient_name_display: str
    patient_name_dicom: str
    patient_id: str
    birth_date: str
    study_date: str
    institution_name: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _seed(global_seed: int, source_id: str) -> int:
    digest = hashlib.sha256(f"{global_seed}|{source_id}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def generate_identity(global_seed: int, source_id: str) -> SyntheticIdentity:
    """Return the same identity for the same seed and source identifier."""

    rng = random.Random(_seed(global_seed, source_id))
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    middle = chr(ord("A") + rng.randrange(26))
    patient_id = f"{rng.randrange(1_000_000, 10_000_000):07d}"
    birth_year = rng.randrange(1930, 2006)
    birth_date = f"{birth_year:04d}{rng.randrange(1, 13):02d}{rng.randrange(1, 29):02d}"
    study_date = f"2025{rng.randrange(1, 13):02d}{rng.randrange(1, 29):02d}"
    case_uuid = str(uuid.UUID(int=rng.getrandbits(128)))
    return SyntheticIdentity(
        case_uuid=f"SYNTH-{case_uuid}",
        patient_name_display=f"{last}, {first} {middle}.",
        patient_name_dicom=f"{last}^{first}^{middle}",
        patient_id=patient_id,
        birth_date=birth_date,
        study_date=study_date,
        institution_name=rng.choice(INSTITUTIONS),
    )
