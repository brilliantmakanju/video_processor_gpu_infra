from models import Subtitle
from utils.text import escape_filter_text

def build_subtitle_filter(subtitle: Subtitle, segment_start: float, 
                         width: int, height: int) -> str:
    """Build professional-looking subtitle filter with background box and thick outline."""
    
    style = subtitle.style
    text = escape_filter_text(subtitle.text)
    
    # Position: default bottom center (85% from top)
    pos = style.get("position", {"x": 50, "y": 85})
    x_pct = pos["x"]   # 0-100 (% of screen width)
    y_pct = pos["y"]   # 0-100 (% of screen height)
    
    # Calculate pixel positions
    base_y = int((y_pct / 100) * height)
    
    # Timing relative to segment start
    sub_end = subtitle.end - segment_start
    sub_start = max(0.0, subtitle.start - segment_start)
    
    # Styling from subtitle.style
    font_size = style.get("fontSize", 38)                  
    outline_width = style.get("strokeWidth", 5)              
    text_align = style.get("textAlign", "center").lower()
    primary_color = style.get("color", "#FFFFFF").lstrip("#")   
    outline_color = style.get("strokeColor", "#000000").lstrip("#")
    
    
    # Horizontal alignment
    if text_align == "center":
        x_expr = "(w-tw)/2"
    elif text_align == "right":
        x_expr = f"w-tw-{int((100 - x_pct)/100 * width)}"
    else:  # left or default
        x_expr = f"{int((x_pct / 100) * width)}"

    # The magic: professional caption style
    return (
        f"drawtext="
        f"x={x_expr}:"
        f"y={base_y}:" 
        f"text='{text}':"
        f"fontsize={font_size}:"
        f"fontcolor=0x{primary_color.upper()}:"
        f"borderw={outline_width}:"
        f"bordercolor=0x{outline_color.upper()}:"
        # Background box: black, 60% opacity, generous padding
        # f"box=1:"
        # f"boxborderw=16:"
        # f"boxcolor=0x000000@0.65:"
        # Only show during subtitle timing
        f"enable='between(t,{sub_start:.3f},{sub_end:.3f})'"
    )