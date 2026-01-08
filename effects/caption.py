import os
import tempfile
from typing import Dict
from models import Subtitle

# Track temp ASS files for cleanup
_ASS_FILE_CACHE: Dict[str, bool] = {}


# =========================
# PUBLIC API
# =========================

def build_subtitle_filter(
    subtitle: Subtitle,
    segment_start: float,
    width: int,
    height: int,
) -> str:
    """
    Build a SAFE FFmpeg subtitles filter (CPU-only).
    MUST be placed BEFORE hwupload_cuda in the filtergraph.
    """

    ass_path = _create_single_subtitle_ass(
        subtitle=subtitle,
        segment_start=segment_start,
        width=width,
        height=height,
    )

    _ASS_FILE_CACHE[ass_path] = True

    # FFmpeg filtergraphs do NOT need shell-style escaping.
    # Absolute paths without quotes are correct.
    return f"subtitles={ass_path}"


def cleanup_subtitle_files() -> None:
    """Remove all temporary ASS subtitle files."""
    for path in list(_ASS_FILE_CACHE.keys()):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception as exc:
            print(f"[WARN] Failed to delete ASS file {path}: {exc}")

    _ASS_FILE_CACHE.clear()


# =========================
# INTERNALS
# =========================

def _create_single_subtitle_ass(
    subtitle: Subtitle,
    segment_start: float,
    width: int,
    height: int,
) -> str:
    """Generate a minimal, valid ASS file for one subtitle event."""

    style = subtitle.style or {}
    text = subtitle.text or ""

    # ---- Timing ----
    start = max(0.0, subtitle.start - segment_start)
    end = max(start + 0.01, subtitle.end - segment_start)

    start_ass = _format_ass_time(start)
    end_ass = _format_ass_time(end)

    # ---- Positioning ----
    pos = style.get("position", {"x": 50, "y": 85})
    x_pct = float(pos.get("x", 50))
    y_pct = float(pos.get("y", 85))

    margin_v = int((y_pct / 100.0) * height)

    # ---- Alignment ----
    align_map = {
        "left": 1,
        "center": 2,
        "right": 3,
    }
    align_h = align_map.get(style.get("textAlign", "center").lower(), 2)

    if y_pct < 33:
        alignment = align_h + 6  # top row (7–9)
    elif y_pct > 66:
        alignment = align_h      # bottom row (1–3)
    else:
        alignment = align_h + 3  # middle row (4–6)

    # ---- Styling ----
    font_size = int(style.get("fontSize", 38))
    outline_width = int(style.get("strokeWidth", 4))

    primary = _hex_to_ass(style.get("color", "#FFFFFF"))
    outline = _hex_to_ass(style.get("strokeColor", "#000000"))

    # ---- Text sanitation ----
    text = (
        text.replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\n", r"\N")
            .replace("\r", "")
    )

    # ---- Create ASS file ----
    fd, ass_path = tempfile.mkstemp(
        prefix="subtitle_",
        suffix=".ass",
        dir="/tmp",
        text=True,
    )

    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            f"PlayResX: {width}\n"
            f"PlayResY: {height}\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n\n"
        )

        f.write(
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
            " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
            " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
            " Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )

        f.write(
            f"Style: Default,Arial,{font_size},{primary},{primary},{outline},"
            "&H80000000,-1,0,0,0,100,100,0,0,1,"
            f"{outline_width},0,{alignment},20,20,{margin_v},1\n\n"
        )

        f.write(
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n"
        )

    return ass_path


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to H:MM:SS.CS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass(color: str) -> str:
    """Convert #RRGGBB → ASS &H00BBGGRR"""
    color = color.lstrip("#")
    r, g, b = color[0:2], color[2:4], color[4:6]
    return f"&H00{b}{g}{r}"


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