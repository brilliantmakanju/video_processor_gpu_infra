from models import Edit
from typing import Optional

def build_zoom_filter(edit: Edit, width: int, height: int) -> Optional[str]:
    """
    GPU-native zoom using crop_cuda + scale_cuda.
    This filter is SAFE for pure CUDA pipelines.
    """

    if edit.zoom == "none" or edit.zoom <= 1.0:
        return None

    zoom_level = float(edit.zoom)
    anchor_x = float(edit.anchor_x)
    anchor_y = float(edit.anchor_y)

    # Compute crop size
    crop_w = int(width / zoom_level)
    crop_h = int(height / zoom_level)

    # Compute top-left crop origin
    crop_x = int(anchor_x * width - crop_w / 2)
    crop_y = int(anchor_y * height - crop_h / 2)

    # Clamp to frame bounds
    crop_x = max(0, min(crop_x, width - crop_w))
    crop_y = max(0, min(crop_y, height - crop_h))

    return (
        f"crop_cuda={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale_cuda={width}:{height}"
    )
