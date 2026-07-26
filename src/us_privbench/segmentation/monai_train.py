"""Small MONAI training loop for reproducible CPU smoke experiments."""

from pathlib import Path
import json

import numpy as np

from us_privbench.segmentation.baseline import binary_metrics, dice_score, lesion_mask
from us_privbench.synthetic.dicom import make_source_pixels
from us_privbench.segmentation.monai_backend import build_model, build_unet
from us_privbench.data.image_dataset import ManifestImageDataset
from us_privbench.data.manifest import CaseRecord, validate_patient_disjoint


def _bootstrap_ci(values: list[float], *, seed: int = 7, samples: int = 10000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        return [values[0], values[0]]
    rng = np.random.default_rng(seed)
    draws = rng.choice(np.asarray(values, dtype=float), (samples, len(values)), replace=True)
    means = draws.mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def train_synthetic_smoke(*, output_dir: str | Path, epochs: int = 2, seed: int = 7) -> dict[str, float | int | str]:
    """Train a tiny U-Net on deterministic synthetic cases and save its checkpoint."""
    try:
        import torch
        from monai.losses import DiceCELoss
    except ImportError as exc:
        raise RuntimeError("Install the optional 'ai' extra to run MONAI training") from exc

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    size = 64
    train_cases = [make_source_pixels(seed + index, width=size, height=size) for index in range(4)]
    validation_cases = [make_source_pixels(seed + 100 + index, width=size, height=size) for index in range(2)]
    truth = torch.from_numpy(lesion_mask(size, size)).float().unsqueeze(0).unsqueeze(0)
    model = build_unet()
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = DiceCELoss(sigmoid=True)
    final_loss = 0.0
    for _ in range(epochs):
        for pixels in train_cases:
            image = torch.from_numpy(pixels).float().unsqueeze(0).unsqueeze(0) / 255.0
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(image), truth)
            loss.backward()
            optimizer.step()
            final_loss = float(loss.detach())

    model.eval()
    scores = []
    with torch.no_grad():
        for pixels in validation_cases:
            image = torch.from_numpy(pixels).float().unsqueeze(0).unsqueeze(0) / 255.0
            prediction = (torch.sigmoid(model(image)) >= 0.5).cpu().numpy()[0, 0]
            scores.append(dice_score(prediction, truth.numpy()[0, 0]))
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / "monai-smoke-best.pt"
    torch.save(model.state_dict(), checkpoint)
    return {
        "epochs": epochs,
        "train_cases": len(train_cases),
        "validation_cases": len(validation_cases),
        "final_loss": final_loss,
        "validation_dice": float(np.mean(scores)),
        "checkpoint": str(checkpoint),
    }


def train_manifest(
    records: list[CaseRecord],
    *,
    output_dir: str | Path,
    epochs: int = 10,
    image_size: int = 256,
    batch_size: int = 4,
    limit_train: int | None = None,
    limit_validation: int | None = None,
    limit_test: int | None = None,
    loss_name: str = "dicece",
    augment: bool = True,
    architecture: str = "unet",
    seed: int = 7,
) -> dict[str, float | int | str]:
    """Train on local manifest paths after enforcing patient disjointness."""
    import torch
    from monai.losses import DiceCELoss, DiceFocalLoss

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    validate_patient_disjoint(records)
    train_records = [record for record in records if record.split == "train"]
    validation_records = [record for record in records if record.split == "validation"]
    test_records = [record for record in records if record.split == "test"]
    if limit_train is not None:
        train_records = train_records[:limit_train]
    if limit_validation is not None:
        validation_records = validation_records[:limit_validation]
    if limit_test is not None:
        test_records = test_records[:limit_test]
    if not train_records or not validation_records:
        raise ValueError("manifest training requires non-empty train and validation splits")
    train_loader = torch.utils.data.DataLoader(ManifestImageDataset(train_records, size=image_size, augment=augment), batch_size=batch_size, shuffle=True)
    validation_loader = torch.utils.data.DataLoader(ManifestImageDataset(validation_records, size=image_size), batch_size=batch_size)
    test_loader = torch.utils.data.DataLoader(ManifestImageDataset(test_records, size=image_size), batch_size=batch_size) if test_records else None
    model = build_model(architecture=architecture)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    if loss_name == "dicece":
        loss_fn = DiceCELoss(sigmoid=True)
    elif loss_name == "dicefocal":
        loss_fn = DiceFocalLoss(sigmoid=True)
    else:
        raise ValueError(f"unsupported loss_name: {loss_name}")
    best_dice = -1.0
    best_state = None
    final_loss = 0.0
    for _ in range(epochs):
        model.train()
        for images, masks in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(images), masks)
            loss.backward()
            optimizer.step()
            final_loss = float(loss.detach())
        model.eval()
        scores = []
        with torch.no_grad():
            for images, masks in validation_loader:
                predictions = (torch.sigmoid(model(images)) >= 0.5).numpy()
                for prediction, mask in zip(predictions[:, 0], masks.numpy()[:, 0]):
                    scores.append(binary_metrics(prediction, mask))
        validation_dice = float(np.mean([score["dice"] for score in scores]))
        if validation_dice > best_dice:
            best_dice = validation_dice
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / f"{architecture}-best.pt"
    if best_state is not None:
        model.load_state_dict(best_state)
    torch.save(model.state_dict(), checkpoint)
    test_metrics = None
    if test_loader is not None:
        model.eval()
        test_scores = []
        with torch.no_grad():
            for images, masks in test_loader:
                predictions = (torch.sigmoid(model(images)) >= 0.5).numpy()
                for prediction, mask in zip(predictions[:, 0], masks.numpy()[:, 0]):
                    test_scores.append(binary_metrics(prediction, mask))
        test_metrics = {f"test_{name}": float(np.mean([score[name] for score in test_scores])) for name in test_scores[0]}
    destination = Path(output_dir)
    per_case_path = None
    patient_metrics = None
    if test_metrics:
        per_case = [
            {"case_id": record.case_id, "patient_group": record.patient_group, "split": record.split, **score}
            for record, score in zip(test_records, test_scores)
        ]
        per_case_path = destination / "test-per-case.json"
        per_case_path.write_text(json.dumps({"records": per_case}, indent=2), encoding="utf-8")
        grouped: dict[str, list[dict]] = {}
        for row in per_case:
            grouped.setdefault(row["patient_group"], []).append(row)
        patient_metrics = {}
        for name in test_scores[0]:
            values = [float(np.mean([row[name] for row in rows])) for rows in grouped.values()]
            patient_metrics[name] = {
                "groups": len(values),
                "mean": float(np.mean(values)),
                "sample_std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "bootstrap_ci95": _bootstrap_ci(values),
            }
    result = {"architecture": architecture, "seed": seed, "epochs": epochs, "train_cases": len(train_records), "validation_cases": len(validation_records), "test_cases": len(test_records), "loss": loss_name, "augment": augment, "final_loss": final_loss, "validation_dice": best_dice, "test_dice": test_metrics["test_dice"] if test_metrics else None, "checkpoint": str(checkpoint)}
    if test_metrics:
        result.update(test_metrics)
        result["test_per_case"] = str(per_case_path)
        result["patient_group_metrics"] = patient_metrics
    return result
