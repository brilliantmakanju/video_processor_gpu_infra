from typing import List

def build_speed_filters(speed_val: float, has_audio: bool) -> tuple[str, List[str]]:
    """Build video and audio filters for speed changes."""
    v_filter = f"setpts={1/speed_val}*PTS"
    a_filters = []
    
    if has_audio:
        val = speed_val
        while val > 2.0:
            a_filters.append("atempo=2.0")
            val /= 2.0
        while val < 0.5:
            a_filters.append("atempo=0.5")
            val *= 2.0
        if 0.5 <= val <= 2.0 and val != 1.0:
            a_filters.append(f"atempo={val}")
            
    return v_filter, a_filters
