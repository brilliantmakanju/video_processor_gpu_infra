from models import Segment
from typing import List, Optional
from effects.zoom import build_zoom_filter
from effects.speed import build_speed_filters
from effects.caption import build_subtitle_filter
# from effects.color import build_improved_color_filter

def get_segment_filters(seg: Segment, width: int, height: int, has_audio: bool) -> tuple[List[str], List[str]]:
    """
    Collect all filters for a segment using a plugin-like approach.
    Returns (video_filters, audio_filters).
    """
    v_filters = []
    a_filters = []

    # 1. Color Grading (Global Effect)
    # color = build_improved_color_filter()
    # if color:
    #     v_filters.append(color)

    # 2. Edit-based Effects
    if seg.edit:
        edit = seg.edit
        
        # Speed
        if edit.speed != 1.0:
            v_speed, a_speed = build_speed_filters(edit.speed, has_audio)
            v_filters.append(v_speed)
            a_filters.extend(a_speed)
        
        # Zoom
        if edit.type == "zoom" or (edit.zoom not in ["none", 1.0]):
            zoom = build_zoom_filter(edit, width, height)
            if zoom:
                v_filters.append(zoom)
        

    # 3. Subtitles
    seen_subs = set()
    for subtitle in seg.subtitles:
        sub_key = (subtitle.text, subtitle.start, subtitle.end)
        if sub_key not in seen_subs:
            v_filters.append(build_subtitle_filter(subtitle, seg.start, width, height))
            seen_subs.add(sub_key)

    return v_filters, a_filters
