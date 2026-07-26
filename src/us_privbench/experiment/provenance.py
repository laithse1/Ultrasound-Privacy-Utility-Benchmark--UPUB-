"""Write reproducibility metadata beside every training result."""

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import platform
import sys


def manifest_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_provenance(output_dir: str | Path, *, manifest: str | Path, config: dict) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "manifest": str(Path(manifest).resolve()),
        "manifest_sha256": manifest_sha256(manifest),
        "config": config,
    }
    path = destination / "provenance.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
