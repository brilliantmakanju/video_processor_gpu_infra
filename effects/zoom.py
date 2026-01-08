from models import Edit
from typing import Optional

def build_zoom_filter(edit: Edit, width: int, height: int) -> Optional[str]:
    """Build instant, stable zoom filter."""
    if edit.zoom == "none" or edit.zoom <= 1.0:
        return None

    zoom_level = float(edit.zoom)
    anchor_x = float(edit.anchor_x)
    anchor_y = float(edit.anchor_y)

    crop_w = int(width / zoom_level)
    crop_h = int(height / zoom_level)
    crop_x = int(anchor_x * width - crop_w / 2)
    crop_y = int(anchor_y * height - crop_h / 2)

    crop_x = max(0, min(crop_x, width - crop_w))
    crop_y = max(0, min(crop_y, height - crop_h))

    return (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={width}:{height}:flags=lanczos"
    )
