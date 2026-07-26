"""PyTorch implementation of the AAU-Net HAAM building block.

The implementation follows the authors' public TensorFlow reference:
parallel dilated/5x5 branches, channel complement attention, spatial
complement attention, and HAAM replacement of ordinary U-Net convolution
blocks. Width is configurable and defaults to a CPU-friendly research build.
"""

import torch
from torch import nn


class HAAM(nn.Module):
    """Hybrid adaptive attention module from the AAU-Net design."""

    def __init__(self, in_channels: int, channels: int, kernel_size: int = 3):
        super().__init__()
        self.channel_dilated = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=3, dilation=3, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.channel_wide = nn.Sequential(
            nn.Conv2d(in_channels, channels, 5, padding=2, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        hidden = max(channels // 4, 4)
        self.channel_gate = nn.Sequential(
            nn.Linear(channels * 2, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, channels),
            nn.Sigmoid(),
        )
        self.channel_fuse = nn.Sequential(
            nn.Conv2d(channels * 2, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.spatial = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.spatial_gate = nn.Sequential(
            nn.Conv2d(channels, 1, 1),
            nn.Sigmoid(),
        )
        self.spatial_fuse = nn.Sequential(
            nn.Conv2d(channels * 2, channels, kernel_size, padding=kernel_size // 2, bias=False),
            nn.BatchNorm2d(channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        dilated = self.channel_dilated(x)
        wide = self.channel_wide(x)
        descriptor = torch.cat((dilated.mean(dim=(2, 3)), wide.mean(dim=(2, 3))), dim=1)
        gate = self.channel_gate(descriptor).unsqueeze(-1).unsqueeze(-1)
        channel_data = self.channel_fuse(torch.cat((dilated * gate, wide * (1.0 - gate)), dim=1))

        spatial_data = self.spatial(x)
        spatial_gate = self.spatial_gate(torch.relu(channel_data + spatial_data))
        fused = torch.cat((channel_data * spatial_gate, spatial_data * (1.0 - spatial_gate)), dim=1)
        return self.spatial_fuse(fused)


class AAUNet(nn.Module):
    """AAU-Net-style encoder/decoder with HAAM in every U-Net stage."""

    def __init__(self, in_channels: int = 1, out_channels: int = 1, features=(8, 16, 32, 64, 128)):
        super().__init__()
        self.encoders = nn.ModuleList()
        previous = in_channels
        for channels in features:
            self.encoders.append(HAAM(previous, channels))
            previous = channels
        self.pools = nn.ModuleList(nn.MaxPool2d(2) for _ in features[:-1])
        self.upconvs = nn.ModuleList()
        self.decoders = nn.ModuleList()
        for index in range(len(features) - 2, -1, -1):
            self.upconvs.append(nn.ConvTranspose2d(features[index + 1], features[index], 2, stride=2))
            self.decoders.append(HAAM(features[index] * 2, features[index]))
        self.head = nn.Conv2d(features[0], out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for index, encoder in enumerate(self.encoders):
            x = encoder(x)
            skips.append(x)
            if index < len(self.pools):
                x = self.pools[index](x)
        skips = skips[:-1][::-1]
        for upconv, decoder, skip in zip(self.upconvs, self.decoders, skips):
            x = upconv(x)
            if x.shape[-2:] != skip.shape[-2:]:
                x = nn.functional.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = decoder(torch.cat((skip, x), dim=1))
        return self.head(x)
