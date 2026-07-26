"""Small atomic file store used by the local research deployment.

This is intentionally not presented as a production database. It provides a
durable, content-addressed boundary for local experiments and a shared queue
between the API and worker containers. A deployment handling sensitive data
must replace or harden this store with authenticated durable storage.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class LocalArtifactStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.getenv("UPUB_ARTIFACT_ROOT", "artifacts/runtime"))
        self.cases = self.root / "cases"
        self.jobs = self.root / "jobs"
        self.objects = self.root / "objects"
        for directory in (self.cases, self.jobs, self.objects):
            directory.mkdir(parents=True, exist_ok=True)

    def put_json(self, payload: dict[str, Any], *, namespace: str, key: str) -> str:
        directory = self.cases if namespace == "cases" else self.jobs
        destination = directory / f"{key}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        temporary.replace(destination)
        return str(destination)

    def get_json(self, *, namespace: str, key: str) -> dict[str, Any] | None:
        directory = self.cases if namespace == "cases" else self.jobs
        path = directory / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_json(self, *, namespace: str) -> list[dict[str, Any]]:
        directory = self.cases if namespace == "cases" else self.jobs
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]

    def put_bytes(self, content: bytes, *, suffix: str = "bin") -> dict[str, str | int]:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.objects / f"{digest}.{suffix}"
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(content)
            temporary.replace(destination)
        return {"sha256": digest, "uri": str(destination), "size": len(content)}
