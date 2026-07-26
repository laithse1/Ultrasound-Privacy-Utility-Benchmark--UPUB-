"""Durable local job worker for the research deployment."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

from us_privbench.storage.local import LocalArtifactStore


def _answer_key(payload: dict):
    from us_privbench.synthetic.answer_key import PixelOverlayTruth, SyntheticAnswerKey
    from us_privbench.synthetic.identity import SyntheticIdentity

    identity = SyntheticIdentity(**payload["identity"])
    overlays = tuple(PixelOverlayTruth(**row) for row in payload["overlays"])
    return SyntheticAnswerKey(
        case_id=payload["case_id"], source_id=payload["source_id"], seed=payload["seed"],
        image_width=payload["image_width"], image_height=payload["image_height"],
        identity=identity, overlays=overlays,
    )


def _job_directory(store: LocalArtifactStore, job: dict) -> Path:
    directory = Path(job.get("config", {}).get("output_dir", store.root / "job-artifacts" / job["job_id"]))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _execute_synthetic(store: LocalArtifactStore, job: dict) -> dict:
    from us_privbench.synthetic.dicom import generate_case

    config = job.get("config", {})
    output = _job_directory(store, job)
    generated = generate_case(output, job["case_id"], config.get("source_id", job["case_id"]), int(config.get("seed", "7")))
    answer_key = output / "answer-key.json"
    answer_key.write_text(__import__("json").dumps(generated.answer_key.as_dict(), indent=2), encoding="utf-8")
    return {
        "adapter_status": "executed",
        "message": "Synthetic source and PHI-injected DICOM artifacts generated.",
        "artifacts": {
            "source": str(generated.source_path),
            "injected": str(generated.injected_path),
            "answer_key": str(answer_key),
        },
    }


def _execute_deidentify(store: LocalArtifactStore, job: dict) -> dict:
    from us_privbench.synthetic.dicom import deidentify_case

    config = job.get("config", {})
    input_path = Path(config["input_path"])
    key_path = Path(config["answer_key_path"])
    default_output = _job_directory(store, job) / "deidentified.dcm"
    requested_output = config.get("output_path", "").strip()
    # Browser users may enter a Windows host path, but the worker runs in
    # Linux. Keep the result in the shared artifact volume instead of writing
    # to the worker container's private filesystem.
    if requested_output and (":" in requested_output or "\\" in requested_output):
        output = default_output
        output_warning = " Host output path was replaced with the shared artifact path."
    else:
        output = Path(requested_output) if requested_output else default_output
        output_warning = ""
    key = _answer_key(__import__("json").loads(key_path.read_text(encoding="utf-8")))
    deidentify_case(input_path, output, key)
    return {"adapter_status": "executed", "message": "DICOM de-identification completed." + output_warning, "artifacts": {"deidentified": str(output)}}


def _execute_segment(store: LocalArtifactStore, job: dict) -> dict:
    import numpy as np
    import torch
    from PIL import Image

    from us_privbench.data.image_dataset import load_grayscale
    from us_privbench.segmentation.baseline import binary_metrics
    from us_privbench.segmentation.monai_backend import build_model

    config = job.get("config", {})
    image_path = Path(config["input_path"])
    mask_path = Path(config["mask_path"])
    checkpoint = Path(config["checkpoint"])
    size = int(config.get("image_size", "128"))
    output = _job_directory(store, job)
    model = build_model(architecture=config.get("architecture", "unet"))
    model.load_state_dict(torch.load(checkpoint, map_location="cpu"))
    model.eval()
    image = load_grayscale(image_path, size=size)
    mask = load_grayscale(mask_path, size=size, mask=True)
    tensor = torch.from_numpy(image).float().unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        prediction = (torch.sigmoid(model(tensor)) >= 0.5).numpy()[0, 0].astype(np.uint8)
    prediction_path = output / "prediction.png"
    Image.fromarray(prediction * 255).save(prediction_path)
    metrics = binary_metrics(prediction, mask)
    return {
        "adapter_status": "executed",
        "message": "Single-case MONAI segmentation completed.",
        "metrics": {f"test_{key}": float(value) for key, value in metrics.items()},
        "artifacts": {"prediction": str(prediction_path)},
    }


def _execute_evaluate(store: LocalArtifactStore, job: dict) -> dict:
    import numpy as np
    import torch

    from us_privbench.data.image_dataset import ManifestImageDataset
    from us_privbench.data.manifest import read_manifest
    from us_privbench.segmentation.baseline import binary_metrics
    from us_privbench.segmentation.monai_backend import build_model

    config = job.get("config", {})
    manifest_path = Path(config["manifest"])
    checkpoint = Path(config["checkpoint"])
    size = int(config.get("image_size", "128"))
    batch_size = int(config.get("batch_size", "32"))
    limit_test = int(config["limit_test"]) if config.get("limit_test") else None
    records = [record for record in read_manifest(manifest_path) if record.split == "test"]
    if limit_test is not None:
        records = records[:limit_test]
    if not records:
        raise ValueError("evaluation requires a non-empty test split")
    loader = torch.utils.data.DataLoader(ManifestImageDataset(records, size=size), batch_size=batch_size)
    model = build_model(architecture=config.get("architecture", "unet"))
    model.load_state_dict(torch.load(checkpoint, map_location="cpu"))
    model.eval()
    scores = []
    with torch.no_grad():
        for images, masks in loader:
            predictions = (torch.sigmoid(model(images)) >= 0.5).numpy()
            for prediction, mask in zip(predictions[:, 0], masks.numpy()[:, 0]):
                scores.append(binary_metrics(prediction, mask))
    metrics = {f"test_{name}": float(np.mean([score[name] for score in scores])) for name in scores[0]}
    result_path = _job_directory(store, job) / "evaluation.json"
    result_path.write_text(__import__("json").dumps({
        "mode": "dataset_test_evaluation",
        "manifest": str(manifest_path),
        "checkpoint": str(checkpoint),
        "test_cases": len(records),
        "target_dataset": records[0].dataset_name,
        "target_version": records[0].dataset_version,
        "metrics": metrics,
    }, indent=2), encoding="utf-8")
    return {
        "adapter_status": "executed",
        "message": "Dataset test-split evaluation completed without target training or checkpoint selection.",
        "metrics": metrics,
        "artifacts": {"evaluation": str(result_path)},
    }


def execute_job(store: LocalArtifactStore, job: dict) -> dict:
    """Execute a job and return an auditable result."""
    job_type = job["job_type"]
    if job_type not in {"synthetic_phi", "deidentify", "segment", "evaluate"}:
        raise ValueError(f"unsupported job type: {job_type}")
    result = {
        "job_id": job["job_id"],
        "case_id": job["case_id"],
        "job_type": job_type,
        "status": "completed",
        "adapter_status": "contract_acknowledged",
        "message": "Artifact-specific execution adapter is required for this job configuration.",
        "completed_at": datetime.now(UTC).isoformat(),
    }
    if job_type == "synthetic_phi" and job.get("config", {}).get("execute", "false").lower() == "true":
        result.update(_execute_synthetic(store, job))
    elif job_type == "deidentify" and job.get("config", {}).get("execute", "false").lower() == "true":
        result.update(_execute_deidentify(store, job))
    elif job_type == "segment" and job.get("config", {}).get("execute", "false").lower() == "true":
        result.update(_execute_segment(store, job))
    elif job_type == "evaluate" and job.get("config", {}).get("execute", "false").lower() == "true":
        result.update(_execute_evaluate(store, job))
    return result


def process_once(store: LocalArtifactStore) -> int:
    processed = 0
    for job in store.list_json(namespace="jobs"):
        if job.get("status") != "queued":
            continue
        job["status"] = "running"
        job["started_at"] = datetime.now(UTC).isoformat()
        store.put_json(job, namespace="jobs", key=job["job_id"])
        try:
            result = execute_job(store, job)
            job.update(result)
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            job.update({"status": "failed", "error": str(exc), "completed_at": datetime.now(UTC).isoformat()})
        store.put_json(job, namespace="jobs", key=job["job_id"])
        print(
            f"UPUB job {job['job_id']} {job['job_type']} {job['status']}"
            + (f": {job['error']}" if job.get("error") else ""),
            flush=True,
        )
        processed += 1
    return processed


def main() -> None:
    store = LocalArtifactStore()
    print(f"UPUB worker ready; artifact root={store.root}", flush=True)
    interval = float(os.getenv("UPUB_WORKER_INTERVAL_SECONDS", "5"))
    while True:
        process_once(store)
        time.sleep(interval)


if __name__ == "__main__":
    main()
