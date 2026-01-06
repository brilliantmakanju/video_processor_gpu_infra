import hashlib
from models import Segment

def get_segment_hash(seg: Segment, input_path: str) -> str:
    """Generate unique hash for segment caching."""
    data = f"{input_path}_{seg.start}_{seg.end}_{seg.is_original}_{len(seg.subtitles)}"
    if seg.edit:
        data += f"_{seg.edit.type}_{seg.edit.speed}_{seg.edit.zoom}"
    return hashlib.md5(data.encode()).hexdigest()[:12]
