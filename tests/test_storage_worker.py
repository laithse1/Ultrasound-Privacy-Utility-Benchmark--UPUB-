from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from us_privbench.storage.local import LocalArtifactStore
from us_privbench.data.manifest import CaseRecord, write_manifest
from us_privbench.worker.main import process_once
from scripts.aggregate_experiment_results import bootstrap_interval
from scripts.ingest_bus_uclm import build_records


def test_local_store_content_addresses_objects(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "runtime")
    first = store.put_bytes(b"upub", suffix="txt")
    second = store.put_bytes(b"upub", suffix="txt")
    assert first == second
    assert first["size"] == 4


def test_worker_completes_durable_contract_job(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "runtime")
    job_id = str(uuid4())
    store.put_json(
        {
            "job_id": job_id,
            "job_type": "evaluate",
            "case_id": "case-001",
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "config": {},
        },
        namespace="jobs",
        key=job_id,
    )
    assert process_once(store) == 1
    result = store.get_json(namespace="jobs", key=job_id)
    assert result["status"] == "completed"
    assert result["adapter_status"] == "contract_acknowledged"


def test_worker_executes_synthetic_phi_job(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "runtime")
    job_id = str(uuid4())
    store.put_json(
        {
            "job_id": job_id,
            "job_type": "synthetic_phi",
            "case_id": "synthetic-worker-case",
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "config": {"execute": "true", "seed": "7"},
        },
        namespace="jobs",
        key=job_id,
    )
    assert process_once(store) == 1
    result = store.get_json(namespace="jobs", key=job_id)
    assert result["status"] == "completed"
    assert result["adapter_status"] == "executed"
    assert Path(result["artifacts"]["injected"]).exists()
    assert Path(result["artifacts"]["answer_key"]).exists()


def test_worker_executes_single_case_segmentation_job(tmp_path) -> None:
    import torch
    from PIL import Image
    from us_privbench.segmentation.monai_backend import build_model

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.new("L", (32, 32), 0).save(image_path)
    Image.new("L", (32, 32), 0).save(mask_path)
    checkpoint = tmp_path / "unet.pt"
    torch.save(build_model().state_dict(), checkpoint)
    store = LocalArtifactStore(tmp_path / "runtime")
    job_id = str(uuid4())
    store.put_json(
        {
            "job_id": job_id,
            "job_type": "segment",
            "case_id": "seg-worker-case",
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "config": {
                "execute": "true", "input_path": str(image_path), "mask_path": str(mask_path),
                "checkpoint": str(checkpoint), "image_size": "32",
            },
        },
        namespace="jobs",
        key=job_id,
    )
    assert process_once(store) == 1
    result = store.get_json(namespace="jobs", key=job_id)
    assert result["status"] == "completed"
    assert result["adapter_status"] == "executed"
    assert "test_dice" in result["metrics"]
    assert Path(result["artifacts"]["prediction"]).exists()


def test_worker_executes_dataset_evaluation_job(tmp_path) -> None:
    import torch
    from PIL import Image
    from us_privbench.segmentation.monai_backend import build_model

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.new("L", (32, 32), 0).save(image_path)
    Image.new("L", (32, 32), 0).save(mask_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest([CaseRecord("test-case", "patient-test", "test", str(image_path), str(mask_path), "demo", "1")], manifest_path)
    checkpoint = tmp_path / "unet.pt"
    torch.save(build_model().state_dict(), checkpoint)
    store = LocalArtifactStore(tmp_path / "runtime")
    job_id = str(uuid4())
    store.put_json(
        {
            "job_id": job_id, "job_type": "evaluate", "case_id": "test-case",
            "status": "queued", "created_at": datetime.now(UTC).isoformat(),
            "config": {"execute": "true", "manifest": str(manifest_path), "checkpoint": str(checkpoint), "image_size": "32", "limit_test": "1"},
        }, namespace="jobs", key=job_id,
    )
    assert process_once(store) == 1
    result = store.get_json(namespace="jobs", key=job_id)
    assert result["status"] == "completed"
    assert result["adapter_status"] == "executed"
    assert 0.0 <= result["metrics"]["test_specificity"] <= 1.0
    assert Path(result["artifacts"]["evaluation"]).exists()


def test_bootstrap_interval_is_reproducible() -> None:
    first = bootstrap_interval([0.2, 0.4, 0.6], seed=7, samples=100)
    second = bootstrap_interval([0.2, 0.4, 0.6], seed=7, samples=100)
    assert first == second


def test_bus_uclm_ingester_keeps_patient_groups_disjoint(tmp_path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "masks").mkdir()
    for name in ("AAAA_01", "BBBB_01", "COPE_01"):
        (tmp_path / "images" / f"{name}.png").write_bytes(b"x")
        (tmp_path / "masks" / f"{name}.png").write_bytes(b"x")
    records = build_records(tmp_path, "test")
    assert {row.split for row in records} == {"train", "validation", "test"}
    assert len({row.patient_group for row in records}) == 3
