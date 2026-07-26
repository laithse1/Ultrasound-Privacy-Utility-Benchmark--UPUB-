from fastapi.testclient import TestClient

from us_privbench.api.main import app, cases, jobs
from us_privbench.synthetic.identity import generate_identity
from us_privbench.synthetic.answer_key import build_answer_key
from us_privbench.synthetic.dicom import deidentify_case, evaluate_deidentification, generate_case
from us_privbench.synthetic.detection import detect_bright_components, evaluate_regions, region_recall
from us_privbench.segmentation.baseline import evaluate_segmentation, lesion_mask
from us_privbench.data.manifest import CaseRecord, read_manifest, validate_patient_disjoint, write_manifest
from us_privbench.data.image_dataset import ManifestImageDataset, load_grayscale


client = TestClient(app)


def setup_function() -> None:
    cases.clear()
    jobs.clear()


def manifest(case_id: str = "demo-case") -> dict:
    return {
        "case_id": case_id,
        "source_uri": "synthetic://demo/source-001",
        "dataset_name": "demo-ultrasound",
        "dataset_version": "0.1",
        "patient_group": "patient-001",
        "split": "test",
        "has_segmentation_mask": True,
    }


def test_health_and_readiness() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_optional_api_key_guard(monkeypatch) -> None:
    monkeypatch.setenv("UPUB_API_KEY", "test-secret")
    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/cases/key-guard-missing").status_code == 401
    assert client.get("/v1/cases/key-guard-missing", headers={"X-API-Key": "test-secret"}).status_code == 404
    monkeypatch.delenv("UPUB_API_KEY")


def test_optional_audit_log_does_not_capture_request_body(monkeypatch, tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("UPUB_AUDIT_LOG", str(audit_path))
    response = client.get("/v1/cases/audit-missing")
    assert response.status_code == 404
    line = audit_path.read_text(encoding="utf-8")
    assert '"method": "GET"' in line
    assert "audit-missing" in line
    assert "source_uri" not in line


def test_register_case_and_submit_job() -> None:
    response = client.post("/v1/cases", json=manifest())
    assert response.status_code == 201
    assert response.json()["case_id"] == "demo-case"

    job_response = client.post(
        "/v1/jobs",
        json={"job_type": "evaluate", "case_id": "demo-case", "config": {"seed": "7"}},
    )
    assert job_response.status_code == 202
    assert job_response.json()["status"] == "queued"

    job_id = job_response.json()["job_id"]
    assert client.get(f"/v1/jobs/{job_id}").json()["case_id"] == "demo-case"


def test_job_requires_registered_case() -> None:
    response = client.post("/v1/jobs", json={"job_type": "segment", "case_id": "missing"})
    assert response.status_code == 404


def test_manifest_rejects_unknown_fields() -> None:
    response = client.post("/v1/cases", json={**manifest(), "patient_name": "should-never-exist"})
    assert response.status_code == 422


def test_synthetic_identity_is_reproducible_and_dicom_shaped() -> None:
    first = generate_identity(7, "source-001")
    second = generate_identity(7, "source-001")
    different = generate_identity(7, "source-002")

    assert first == second
    assert first != different
    assert "^" in first.patient_name_dicom
    assert len(first.patient_id) == 7
    assert first.birth_date.isdigit() and len(first.birth_date) == 8
    assert first.study_date.isdigit() and len(first.study_date) == 8


def test_answer_key_contains_the_same_values_as_identity() -> None:
    identity = generate_identity(7, "source-001")
    answer_key = build_answer_key(
        case_id="case-001",
        source_id="source-001",
        seed=7,
        image_width=640,
        image_height=480,
        identity=identity,
    )

    assert answer_key.as_dict()["identity"]["patient_id"] == identity.patient_id
    assert [row.phi_category for row in answer_key.overlays] == [
        "patient_name",
        "patient_id",
        "study_date",
    ]
    assert [row.dicom_tag for row in answer_key.overlays] == [
        "PatientName",
        "PatientID",
        "StudyDate",
    ]


def test_end_to_end_synthetic_dicom_case(tmp_path) -> None:
    generated = generate_case(tmp_path, "case-001", "source-001", 7)
    deidentified_path = tmp_path / "case-001.deidentified.dcm"
    deidentify_case(generated.injected_path, deidentified_path, generated.answer_key)
    metrics = evaluate_deidentification(
        generated.injected_path, deidentified_path, generated.source_pixels, generated.answer_key
    )

    assert generated.source_path.exists()
    assert generated.injected_path.exists()
    assert metrics["header_clean"] is True
    assert metrics["clinical_pixels_preserved_outside_phi"] is True


def test_synthetic_dicom_uids_are_reproducible(tmp_path) -> None:
    first = generate_case(tmp_path / "first", "case-001", "source-001", 7)
    second = generate_case(tmp_path / "second", "case-001", "source-001", 7)

    import pydicom

    assert pydicom.dcmread(first.injected_path).SOPInstanceUID == pydicom.dcmread(second.injected_path).SOPInstanceUID


def test_explainable_pixel_detector_finds_planted_banner_components(tmp_path) -> None:
    generated = generate_case(tmp_path, "case-001", "source-001", 7)
    import pydicom

    pixels = pydicom.dcmread(generated.injected_path).pixel_array
    candidates = detect_bright_components(pixels, min_area=2)
    truth = [(row.x, row.y, row.width, row.height) for row in generated.answer_key.overlays]
    assert candidates
    # The primitive baseline sees glyph components, not complete text lines.
    # A low-IoU hit is still useful as the pre-OCR sanity baseline.
    assert region_recall(candidates, truth, iou_threshold=0.01) > 0


def test_region_evaluation_is_explicit_about_pre_ocr_limits() -> None:
    truth = [(0, 0, 10, 10)]
    candidates = detect_bright_components(__import__("numpy").zeros((20, 20), dtype="uint8"))
    metrics = evaluate_regions(candidates, truth)
    assert metrics["candidate_count"] == 0
    assert metrics["truth_count"] == 1
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0


def test_segmentation_baseline_reports_privacy_utility_metrics(tmp_path) -> None:
    generated = generate_case(tmp_path, "case-001", "source-001", 7)
    truth = lesion_mask(*generated.source_pixels.shape)
    result = evaluate_segmentation(generated.source_pixels, truth)

    assert result["truth_pixels"] > 0
    assert 0.0 <= result["dice"] <= 1.0
    assert 0.0 <= result["iou"] <= 1.0


def test_manifest_round_trip_and_patient_leakage_guard(tmp_path) -> None:
    records = [
        CaseRecord("a", "patient-a", "train", "synthetic://a"),
        CaseRecord("b", "patient-b", "validation", "synthetic://b"),
    ]
    path = tmp_path / "manifest.json"
    write_manifest(records, path)
    assert read_manifest(path) == records

    leaked = [CaseRecord("x", "patient-x", "train", "synthetic://x"), CaseRecord("y", "patient-x", "test", "synthetic://y")]
    try:
        validate_patient_disjoint(leaked)
    except ValueError as error:
        assert "patient leakage" in str(error)
    else:
        raise AssertionError("expected patient leakage to be rejected")


def test_image_dataset_loads_image_and_mask_with_safe_interpolation(tmp_path) -> None:
    from PIL import Image

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.new("L", (8, 4), 128).save(image_path)
    Image.new("L", (8, 4), 255).save(mask_path)
    record = CaseRecord("case", "patient", "train", str(image_path), str(mask_path))
    dataset = ManifestImageDataset([record], size=16)
    image, mask = dataset[0]
    assert tuple(image.shape) == (1, 16, 16)
    assert tuple(mask.shape) == (1, 16, 16)
    assert set(mask.unique().tolist()) <= {0.0, 1.0}
    assert load_grayscale(image_path, size=16).max() <= 1.0
