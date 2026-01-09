"""
Watermark Effect Module

Applies a watermark (image or animated GIF) to video output.
Supports configurable positioning and sizing.
"""
import os
from typing import Optional, Tuple
from config import (
    WATERMARK_URL, WATERMARK_PADDING, WATERMARK_SCALE,
    WATERMARK_OPACITY, WATERMARK_POSITION, FFMPEG_BIN
)
from utils.ffmpeg import run_ffmpeg
from storage.downloader import download_file


# =============================================================================
# WATERMARK DOWNLOAD
# =============================================================================

def download_watermark(watermark_url: str) -> Optional[str]:
    """Download watermark file and return local path."""
    if not watermark_url:
        return None
    
    # Determine extension from URL
    ext = ".png"
    if ".gif" in watermark_url.lower():
        ext = ".gif"
    elif ".webp" in watermark_url.lower():
        ext = ".webp"
    
    local_path = f"watermark{ext}"
    try:
        download_file(watermark_url, local_path, 8192, 120)
        return local_path
    except Exception:
        return None


# =============================================================================
# POSITION CALCULATOR
# =============================================================================

def calculate_position(position: str, video_width: int, video_height: int, 
                       wm_width: int, padding: int) -> Tuple[str, str]:
    """
    Calculate FFmpeg overlay position expressions.
    Returns (x_expr, y_expr) for overlay filter.
    """
    positions = {
        "top_left": (f"{padding}", f"{padding}"),
        "top_right": (f"W-w-{padding}", f"{padding}"),
        "bottom_left": (f"{padding}", f"H-h-{padding}"),
        "bottom_right": (f"W-w-{padding}", f"H-h-{padding}"),
    }
    return positions.get(position, positions["bottom_left"])


# =============================================================================
# FILTER BUILDER
# =============================================================================

def build_watermark_filter(video_width: int, video_height: int) -> Optional[str]:
    """
    Build FFmpeg filter for watermark overlay.
    Returns filter string or None if watermark not configured.
    """
    if not WATERMARK_URL:
        return None
    
    # Calculate watermark size (percentage of video width)
    wm_width = int(video_width * WATERMARK_SCALE)
    
    # Get position
    x_pos, y_pos = calculate_position(
        WATERMARK_POSITION, video_width, video_height, wm_width, WATERMARK_PADDING
    )
    
    # Build filter - scale watermark and overlay with opacity
    # For GIF: use -ignore_loop 0 in input, not in filter
    scale = f"scale={wm_width}:-1"
    opacity = f"format=rgba,colorchannelmixer=aa={WATERMARK_OPACITY}"
    
    return f"[1:v]{scale},{opacity}[wm];[0:v][wm]overlay={x_pos}:{y_pos}:shortest=1"


def build_watermark_filter_integrated(video_width: int, video_height: int, 
                                      input_label: str = "[v_in]", 
                                      output_label: str = "[v_out]") -> Optional[str]:
    """
    Build FFmpeg filter for watermark overlay to be used in a larger filter complex.
    Assumes watermark is input [1:v].
    """
    if not WATERMARK_URL:
        return None
    
    wm_width = int(video_width * WATERMARK_SCALE)
    x_pos, y_pos = calculate_position(
        WATERMARK_POSITION, video_width, video_height, wm_width, WATERMARK_PADDING
    )
    
    scale = f"scale={wm_width}:-1"
    opacity = f"format=rgba,colorchannelmixer=aa={WATERMARK_OPACITY}"
    
    return f"[1:v]{scale},{opacity}[wm];{input_label}[wm]overlay={x_pos}:{y_pos}:shortest=1{output_label}"


def build_watermark_filter_gpu(video_width: int, video_height: int) -> Optional[str]:
    """
    Build GPU-accelerated FFmpeg filter for watermark overlay.
    Uses overlay_cuda which requires both inputs to be in CUDA memory.
    """
    if not WATERMARK_URL:
        return None
    
    wm_width = int(video_width * WATERMARK_SCALE)
    x_pos, y_pos = calculate_position(
        WATERMARK_POSITION, video_width, video_height, wm_width, WATERMARK_PADDING
    )
    
    # Upload watermark to GPU, scale it there, and overlay
    # Note: overlay_cuda doesn't support shortest=1 in some versions, 
    # but we can use it if available or handle it via input duration.
    # For now, we'll use the basic overlay_cuda syntax.
    scale = f"scale_cuda={wm_width}:-1:format=nv12"
    
    # Opacity on GPU is tricky without custom shaders, so we'll do it on CPU before upload
    opacity = f"format=rgba,colorchannelmixer=aa={WATERMARK_OPACITY}"
    
    return f"[1:v]{opacity},hwupload_cuda,{scale}[wm];[v_in][wm]overlay_cuda={x_pos}:{y_pos}"


# =============================================================================
# APPLY WATERMARK
# =============================================================================

def apply_watermark(input_video: str, output_video: str, 
                    video_width: int, video_height: int,
                    watermark_path: Optional[str] = None) -> bool:
    """
    Apply watermark to video file.
    
    Args:
        input_video: Path to input video
        output_video: Path to output video  
        video_width: Video width for scaling
        video_height: Video height for positioning
        watermark_path: Optional local path to watermark (downloads if None)
    
    Returns:
        True if watermark applied, False otherwise
    """
    # Download watermark if not provided
    if not watermark_path:
        watermark_path = download_watermark(WATERMARK_URL)
    
    if not watermark_path or not os.path.exists(watermark_path):
        return False
    
    # Build filter
    filter_str = build_watermark_filter(video_width, video_height)
    if not filter_str:
        return False
    
    # Determine if GIF (needs special handling)
    is_gif = watermark_path.lower().endswith(".gif")
    
    # Build FFmpeg command
    cmd = [FFMPEG_BIN, "-y"]
    
    # Input video
    cmd.extend(["-i", input_video])
    
    # Watermark input (loop for images and GIFs)
    if is_gif:
        cmd.extend(["-ignore_loop", "0", "-i", watermark_path])
    else:
        # For static images, we MUST loop so shortest=1 works correctly
        cmd.extend(["-loop", "1", "-i", watermark_path])
    
    # Apply filter with explicit output label
    cmd.extend(["-filter_complex", f"{filter_str}[outv]"])
    
    # Output encoding with explicit mapping
    cmd.extend([
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_video
    ])
    
    try:
        run_ffmpeg(cmd, timeout=600)
        return True
    except Exception:
        return False


# =============================================================================
# CLEANUP
# =============================================================================

def cleanup_watermark():
    """Remove downloaded watermark files."""
    for ext in [".png", ".gif", ".webp"]:
        path = f"watermark{ext}"
        if os.path.exists(path):
            os.remove(path)
