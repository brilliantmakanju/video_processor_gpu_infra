from typing import List, Tuple, Dict, Any
from models import Edit, Subtitle, Segment
from config import DEBUG_OVERLAY, ENABLE_COLOR_GRADING

def parse_edit_map(data: Dict[str, Any]) -> Tuple[List[Edit], List[Subtitle]]:
    """Parse JSON into Edit and Subtitle objects with robust error handling."""
    edits = []
    subtitles = []
    
    if not isinstance(data, dict):
        return edits, subtitles

    for e in data.get("edits", []):
        try:
            edits.append(Edit(
                zoom=e.get("zoom", 1.0),
                end=float(e.get("end", 0)),
                type=e.get("type", "zoom"),
                start=float(e.get("start", 0)),
                speed=float(e.get("speed", 1.0)),
                is_locked=e.get("isLocked", False),
                anchor_x=float(e.get("anchorX", 0.5)),
                anchor_y=float(e.get("anchorY", 0.5))
            ))
        except (ValueError, TypeError, KeyError):
            continue # Skip malformed edit
    
    for s in data.get("subtitles", []):
        try:
            subtitles.append(Subtitle(
                style=s.get("style", {}),
                end=float(s.get("end", 0)),
                text=str(s.get("text", "")),
                start=float(s.get("start", 0)),
                is_locked=s.get("isLocked", False)
            ))
        except (ValueError, TypeError, KeyError):
            continue # Skip malformed subtitle
    
    return edits, subtitles

def analyze_segment_processing(seg: Segment, orig_w: int, orig_h: int, 
                               out_w: int, out_h: int) -> Tuple[bool, bool]:
    """Determine if segment needs processing."""
    needs_processing = False
    can_copy = False
    
    if seg.is_original and not seg.subtitles and not DEBUG_OVERLAY:
        if orig_w == out_w and orig_h == out_h and not ENABLE_COLOR_GRADING:
            can_copy = True
            needs_processing = False
        else:
            needs_processing = True
    else:
        needs_processing = True
    
    if seg.edit:
        if seg.edit.speed != 1.0 or seg.edit.zoom not in ["none", 1.0]:
            needs_processing = True
    
    return needs_processing, can_copy
