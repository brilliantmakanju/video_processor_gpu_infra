import os
import tempfile
from typing import List
from models import Subtitle
from utils.text import escape_filter_text

# Global cache for ASS files (cleaned up at end)
_ASS_FILE_CACHE = {}

def build_subtitle_filter(subtitle: Subtitle, segment_start: float, 
                         width: int, height: int) -> str:
    """
    Build text overlay filter using ASS subtitles (works without drawtext filter).
    
    This is a DROP-IN REPLACEMENT - keeps the same interface, but uses ASS format
    internally instead of drawtext. No changes needed to your existing code!
    
    Returns: Filter string to add to your FFmpeg filter chain
    """
    
    # Create a temporary ASS file for this subtitle
    ass_file = _create_single_subtitle_ass(
        subtitle, segment_start, width, height
    )
    
    # Cache it so we can clean up later
    _ASS_FILE_CACHE[ass_file] = True
    
    # Escape path for FFmpeg filter - CRITICAL for special characters
    # Convert backslashes to forward slashes (Windows compatibility)
    escaped_path = ass_file.replace('\\', '/')
    # Escape colons, single quotes, and special characters
    escaped_path = escaped_path.replace(':', r'\:')
    escaped_path = escaped_path.replace("'", r"'\''")  # Proper single quote escaping
    
    # Return subtitles filter with properly escaped path
    return f"subtitles=filename='{escaped_path}'"


def _create_single_subtitle_ass(subtitle: Subtitle, segment_start: float,
                                width: int, height: int) -> str:
    """Create ASS file for a single text overlay."""
    
    style = subtitle.style
    text = subtitle.text
    
    # Position
    pos = style.get("position", {"x": 50, "y": 85})
    x_pct = pos["x"]
    y_pct = pos["y"]
    
    # Timing relative to segment start
    sub_start = max(0.0, subtitle.start - segment_start)
    sub_end = subtitle.end - segment_start
    
    # Styling
    font_size = style.get("fontSize", 38)
    outline_width = style.get("strokeWidth", 5)
    text_align = style.get("textAlign", "center").lower()
    primary_color = style.get("color", "#FFFFFF").lstrip("#")
    outline_color = style.get("strokeColor", "#000000").lstrip("#")
    
    # ASS alignment codes
    # Bottom: 1=left, 2=center, 3=right
    # Middle: 4=left, 5=center, 6=right  
    # Top: 7=left, 8=center, 9=right
    
    # Determine vertical position (top/middle/bottom)
    if y_pct < 33:
        v_align = 7  # Top row
    elif y_pct > 66:
        v_align = 1  # Bottom row
    else:
        v_align = 4  # Middle row
    
    # Add horizontal alignment
    if text_align == "center":
        alignment = v_align + 1
    elif text_align == "right":
        alignment = v_align + 2
    else:  # left
        alignment = v_align
    
    # Convert hex colors to ASS format (ABGR with alpha channel)
    primary_ass = f"&H00{primary_color[4:6]}{primary_color[2:4]}{primary_color[0:2]}"
    outline_ass = f"&H00{outline_color[4:6]}{outline_color[2:4]}{outline_color[0:2]}"
    
    # Calculate vertical margin for precise positioning
    margin_v = int(((100 - y_pct) / 100) * height) if y_pct > 50 else int((y_pct / 100) * height)
    
    # Create temporary ASS file in /tmp with simple name (no special chars)
    # Use prefix that's easy to escape
    fd, ass_path = tempfile.mkstemp(suffix='.ass', prefix='sub_', dir='/tmp', text=True)
    
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write(f"PlayResX: {width}\n")
        f.write(f"PlayResY: {height}\n")
        f.write("WrapStyle: 0\n")
        f.write("ScaledBorderAndShadow: yes\n\n")
        
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # Style with proper outline and positioning
        f.write(f"Style: Default,Arial,{font_size},{primary_ass},{primary_ass},{outline_ass},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},0,{alignment},10,10,{margin_v},1\n\n")
        
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        # Format time
        start_str = _format_ass_time(sub_start)
        end_str = _format_ass_time(sub_end)
        
        # Clean text for ASS
        text_clean = text.replace('\n', '\\N').replace('\r', '')
        
        f.write(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_clean}\n")
    
    return ass_path


def _format_ass_time(seconds: float) -> str:
    """Format seconds as H:MM:SS.CS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def cleanup_subtitle_files():
    """
    Call this after rendering is complete to clean up temporary ASS files.
    Add this to your cleanup code at the end of video processing.
    """
    for ass_file in _ASS_FILE_CACHE.keys():
        try:
            if os.path.exists(ass_file):
                os.unlink(ass_file)
        except Exception as e:
            print(f"Warning: Could not delete {ass_file}: {e}")
    
    _ASS_FILE_CACHE.clear()


# Backwards compatibility - keep the old function signature
def build_subtitle_filter_drawtext(subtitle: Subtitle, segment_start: float, 
                                   width: int, height: int) -> str:
    """
    DEPRECATED: Old drawtext version (doesn't work without drawtext filter).
    Use build_subtitle_filter() instead - it works without drawtext!
    """
    return build_subtitle_filter(subtitle, segment_start, width, height)