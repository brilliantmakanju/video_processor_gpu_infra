from typing import List, Set
from models import Edit, Subtitle, Segment
from processor.analyzer import analyze_segment_processing

def create_segments(edits: List[Edit], subtitles: List[Subtitle], 
                   total_duration: float, orig_w: int, orig_h: int,
                   out_w: int, out_h: int) -> List[Segment]:
    """Create optimized segments, splitting at all edit/cut boundaries."""
    
    # 1. Collect all boundary points
    boundaries: Set[float] = {0.0, total_duration}
    for e in edits:
        boundaries.add(max(0.0, min(e.start, total_duration)))
        boundaries.add(max(0.0, min(e.end, total_duration)))
    
    sorted_points = sorted(list(boundaries))
    segments: List[Segment] = []
    
    # 2. Helper to check if a range is inside a 'cut'
    def is_cut(start: float, end: float) -> bool:
        for e in edits:
            if e.type == "cut" and not (end <= e.start or start >= e.end):
                return True
        return False

    # 3. Create segments between boundaries
    for i in range(len(sorted_points) - 1):
        start, end = sorted_points[i], sorted_points[i+1]
        if end - start < 0.001 or is_cut(start, end):
            continue
            
        # Find active edit and overlapping subtitles
        active_edit = next((e for e in edits if e.type != "cut" and not (end <= e.start or start >= e.end)), None)
        overlapping_subs = [s for s in subtitles if not (s.end <= start or s.start >= end)]
        
        seg = Segment(
            edit=active_edit,
            end=end,
            start=start,
            is_original=(active_edit is None),
            subtitles=overlapping_subs
        )
        seg.needs_processing, seg.can_copy = analyze_segment_processing(seg, orig_w, orig_h, out_w, out_h)
        segments.append(seg)
        
    return segments
