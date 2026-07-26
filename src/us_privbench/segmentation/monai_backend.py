"""Optional MONAI U-Net backend."""


def build_unet(*, in_channels: int = 1, out_channels: int = 1):
    """Build the compact 2D U-Net used by the first learned experiment."""
    try:
        from monai.networks.nets import UNet
    except ImportError as exc:
        raise RuntimeError("Install the optional 'ai' extra to enable MONAI") from exc
    return UNet(
        spatial_dims=2,
        in_channels=in_channels,
        out_channels=out_channels,
        channels=(16, 32, 64, 128),
        strides=(2, 2, 2),
        num_res_units=2,
    )


def build_attention_unet(*, in_channels: int = 1, out_channels: int = 1):
    """Build a compact attention-gated U-Net comparator.

    This is an implementation comparator inspired by the attention-U-Net
    family, not a reimplementation of AAU-Net's hybrid adaptive module.
    Keeping it in the same MONAI/metric contract makes the comparison fair
    while reserving the full AAU-Net reproduction for a later study.
    """
    try:
        from monai.networks.nets import AttentionUnet
    except ImportError as exc:
        raise RuntimeError("Install the optional 'ai' extra to enable MONAI") from exc
    return AttentionUnet(
        spatial_dims=2,
        in_channels=in_channels,
        out_channels=out_channels,
        channels=(16, 32, 64, 128),
        strides=(2, 2, 2),
        kernel_size=3,
        up_kernel_size=3,
    )


def build_aau_net(*, in_channels: int = 1, out_channels: int = 1):
    """Build the UPUB PyTorch AAU-Net-style HAAM implementation."""
    from us_privbench.segmentation.aau_net import AAUNet

    return AAUNet(in_channels=in_channels, out_channels=out_channels)


def build_model(*, architecture: str = "unet", in_channels: int = 1, out_channels: int = 1):
    """Build a named segmentation architecture under the UPUB contract."""
    if architecture == "unet":
        return build_unet(in_channels=in_channels, out_channels=out_channels)
    if architecture == "attention_unet":
        return build_attention_unet(in_channels=in_channels, out_channels=out_channels)
    if architecture == "aau_net":
        return build_aau_net(in_channels=in_channels, out_channels=out_channels)
    raise ValueError(f"unsupported architecture: {architecture}")
