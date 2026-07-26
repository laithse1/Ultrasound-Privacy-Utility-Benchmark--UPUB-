from datetime import UTC, datetime
from enum import StrEnum
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from us_privbench.storage.local import LocalArtifactStore

app = FastAPI(
    title="Ultrasound Privacy Utility Benchmark API",
    version="0.1.0",
    description="Manifest and job API for privacy-preserving ultrasound AI research.",
)


class JobType(StrEnum):
    SYNTHETIC_PHI = "synthetic_phi"
    DEIDENTIFY = "deidentify"
    SEGMENT = "segment"
    EVALUATE = "evaluate"


class CaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    source_uri: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1, max_length=128)
    dataset_version: str = Field(min_length=1, max_length=64)
    patient_group: str = Field(min_length=1, max_length=128)
    split: str = Field(pattern=r"^(train|validation|test)$")
    has_segmentation_mask: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class RegisteredCase(CaseManifest):
    registered_at: datetime


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_type: JobType
    case_id: str = Field(min_length=1, max_length=128)
    config: dict[str, str] = Field(default_factory=dict)


class Job(BaseModel):
    job_id: UUID
    job_type: JobType
    case_id: str
    status: str
    created_at: datetime
    config: dict[str, str]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    message: str | None = None
    adapter_status: str | None = None
    metrics: dict[str, float] | None = None
    artifacts: dict[str, str] | None = None


cases: dict[str, RegisteredCase] = {}
jobs: dict[UUID, Job] = {}
artifact_store = LocalArtifactStore()


def _audit_event(event: dict) -> None:
    destination = os.getenv("UPUB_AUDIT_LOG", "")
    if not destination:
        return
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def _load_persisted_state() -> None:
    for payload in artifact_store.list_json(namespace="cases"):
        registered = RegisteredCase.model_validate(payload)
        cases[registered.case_id] = registered
    for payload in artifact_store.list_json(namespace="jobs"):
        job = Job.model_validate(payload)
        jobs[job.job_id] = job


_load_persisted_state()


@app.middleware("http")
async def optional_api_key(request: Request, call_next):
    """Protect API routes when UPUB_API_KEY is configured for a shared deployment."""
    configured_key = os.getenv("UPUB_API_KEY", "")
    if configured_key and request.url.path.startswith("/v1/"):
        supplied_key = request.headers.get("x-api-key", "")
        if supplied_key != configured_key:
            _audit_event({"timestamp": datetime.now(UTC).isoformat(), "method": request.method, "path": request.url.path, "status": 401})
            return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
    response = await call_next(request)
    if request.url.path.startswith("/v1/"):
        _audit_event({"timestamp": datetime.now(UTC).isoformat(), "method": request.method, "path": request.url.path, "status": response.status_code})
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/dicom/import")
async def import_dicom(request: Request) -> dict:
    """Forward one explicitly selected DICOM instance to the private Orthanc service."""
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="DICOM payload is empty")
    orthanc_url = os.getenv("UPUB_ORTHANC_URL", "http://orthanc:8042").rstrip("/")
    outbound = UrlRequest(
        f"{orthanc_url}/instances",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/dicom"},
    )
    try:
        with urlopen(outbound, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Orthanc rejected the DICOM: {detail}") from error
    except URLError as error:
        raise HTTPException(status_code=503, detail=f"Orthanc is unavailable: {error.reason}") from error


@app.post("/v1/cases", response_model=RegisteredCase, status_code=status.HTTP_201_CREATED)
def register_case(manifest: CaseManifest) -> RegisteredCase:
    if manifest.case_id in cases:
        raise HTTPException(status_code=409, detail="case_id is already registered")
    registered = RegisteredCase(**manifest.model_dump(), registered_at=datetime.now(UTC))
    cases[manifest.case_id] = registered
    artifact_store.put_json(registered.model_dump(mode="json"), namespace="cases", key=manifest.case_id)
    return registered


@app.get("/v1/cases", response_model=list[RegisteredCase])
def list_cases() -> list[RegisteredCase]:
    return sorted(cases.values(), key=lambda item: item.registered_at, reverse=True)


@app.get("/v1/cases/{case_id}", response_model=RegisteredCase)
def get_case(case_id: str) -> RegisteredCase:
    if case_id not in cases:
        persisted = artifact_store.get_json(namespace="cases", key=case_id)
        if persisted:
            cases[case_id] = RegisteredCase.model_validate(persisted)
    if case_id not in cases:
        raise HTTPException(status_code=404, detail="case not found")
    return cases[case_id]


@app.post("/v1/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def submit_job(request: JobRequest) -> Job:
    if request.case_id not in cases:
        raise HTTPException(status_code=404, detail="case not found")
    if request.config.get("execute", "false").lower() == "true":
        required = {
            JobType.DEIDENTIFY: ("input_path", "answer_key_path"),
            JobType.SEGMENT: ("input_path", "mask_path", "checkpoint"),
            JobType.EVALUATE: ("manifest", "checkpoint"),
        }.get(request.job_type, ())
        missing = [name for name in required if not request.config.get(name)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{request.job_type.value} cannot start yet. Missing workflow inputs: "
                    + ", ".join(missing)
                    + ". Registering a browser file only creates a manifest; it does not upload training artifacts."
                ),
            )
    job = Job(
        job_id=uuid4(),
        job_type=request.job_type,
        case_id=request.case_id,
        status="queued",
        created_at=datetime.now(UTC),
        config=request.config,
    )
    jobs[job.job_id] = job
    artifact_store.put_json(job.model_dump(mode="json"), namespace="jobs", key=str(job.job_id))
    return job


@app.get("/v1/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    # The worker updates the durable JSON record in a separate process. Reload
    # before listing so the console sees running/completed/failed transitions.
    current: list[Job] = []
    for payload in artifact_store.list_json(namespace="jobs"):
        job = Job.model_validate(payload)
        jobs[job.job_id] = job
        current.append(job)
    return sorted(current, key=lambda item: item.created_at, reverse=True)


@app.get("/v1/jobs/{job_id}", response_model=Job)
def get_job(job_id: UUID) -> Job:
    if job_id not in jobs:
        persisted = artifact_store.get_json(namespace="jobs", key=str(job_id))
        if persisted:
            jobs[job_id] = Job.model_validate(persisted)
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="job not found")
    persisted = artifact_store.get_json(namespace="jobs", key=str(job_id))
    if persisted:
        jobs[job_id] = Job(**persisted)
    return jobs[job_id]


@app.get("/v1/jobs/{job_id}/artifacts/{artifact_name}")
def download_artifact(job_id: UUID, artifact_name: str):
    """Download a named output recorded by a completed worker job."""
    job = get_job(job_id)
    if not job.artifacts or artifact_name not in job.artifacts:
        raise HTTPException(status_code=404, detail="artifact not found")
    candidate = Path(job.artifacts[artifact_name]).resolve()
    root = artifact_store.root.resolve()
    if root not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="artifact is unavailable")
    return FileResponse(candidate, filename=candidate.name)
