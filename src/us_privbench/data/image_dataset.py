"""Local image/mask dataset adapter for public ultrasound collections."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from us_privbench.data.manifest import CaseRecord


def load_grayscale(path: str | Path, *, size: int = 256, mask: bool = False) -> np.ndarray:
    """Load, orient, and resize an image without corrupting mask labels."""
    image = ImageOps.exif_transpose(Image.open(path)).convert("L")
    interpolation = Image.Resampling.NEAREST if mask else Image.Resampling.BILINEAR
    image = image.resize((size, size), interpolation)
    array = np.asarray(image, dtype=np.float32)
    if mask:
        return (array >= 0.5).astype(np.float32)
    return array / 255.0


class ManifestImageDataset:
    """Lazy dataset compatible with a PyTorch DataLoader."""

    def __init__(self, records: list[CaseRecord], *, size: int = 256, augment: bool = False):
        if any(record.mask_uri is None for record in records):
            raise ValueError("segmentation training requires mask_uri for every record")
        self.records = records
        self.size = size
        self.augment = augment

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        import torch

        record = self.records[index]
        image = load_grayscale(record.image_uri, size=self.size)
        mask = load_grayscale(record.mask_uri, size=self.size, mask=True)
        image_tensor = torch.from_numpy(image).unsqueeze(0)
        mask_tensor = torch.from_numpy(mask).unsqueeze(0)
        if self.augment and torch.rand(()) < 0.5:
            image_tensor = torch.flip(image_tensor, dims=(2,))
            mask_tensor = torch.flip(mask_tensor, dims=(2,))
        return image_tensor, mask_tensor
