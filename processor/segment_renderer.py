import os
from config import (
    FFMPEG_BIN, SMART_COPY_MODE, AUDIO_BITRATE, CQ_QUALITY, 
    MAX_SEGMENT_TIMEOUT, USE_SCALE_CUDA, GPU_SCALE_ALGO
)
from typing import Tuple
from models import Segment
from utils.ffmpeg import run_ffmpeg
from utils.gpu import check_gpu_support, get_gpu_compute_capability
from utils.text import escape_filter_text
from effects.registry import get_segment_filters

def render_segment_smart(args: tuple) -> str:
    (
        i,
        seg,
        input_path,
        temp_dir,
        fps,
        debug_overlay,
        has_audio,
        orig_w,
        orig_h,
        out_w,
        out_h,
    ) = args

    temp_out = os.path.join(temp_dir, f"seg_{i:04d}.mp4")

    # ─────────────────────────────────────────────
    # SMART COPY
    # ─────────────────────────────────────────────
    if seg.can_copy and SMART_COPY_MODE:
        cmd = [
            FFMPEG_BIN, "-y",
            "-ss", str(seg.start),
            "-t", str(seg.duration),
            "-i", input_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            temp_out,
        ]
        run_ffmpeg(cmd)
        return temp_out

    # ─────────────────────────────────────────────
    # GPU availability
    # ─────────────────────────────────────────────
    if not check_gpu_support():
        return _render_cpu_fallback(args, temp_out)

    # ─────────────────────────────────────────────
    # Collect filters
    # ─────────────────────────────────────────────
    reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)

    # ─────────────────────────────────────────────
    # Base FFmpeg command
    # ─────────────────────────────────────────────
    cmd = [
        FFMPEG_BIN, "-y",
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",
        "-hwaccel_device", "0",
        "-extra_hw_frames", "8",
        "-ss", str(seg.start),
        "-t", str(seg.duration),
        "-i", input_path,
    ]

    # ─────────────────────────────────────────────
    # Build filter chain
    # ─────────────────────────────────────────────
    gpu_filters = _build_gpu_filter_chain(
        seg=seg,
        out_w=out_w,
        out_h=out_h,
        orig_w=orig_w,
        orig_h=orig_h,
        has_audio=has_audio,
        debug_overlay=debug_overlay,
        seg_idx=i,
        reg_v=reg_v,
    )

    is_hybrid = "hwdownload" in gpu_filters

    v_chain = ",".join(gpu_filters)

    # ─────────────────────────────────────────────
    # ALWAYS use filter_complex (NO -vf)
    # ─────────────────────────────────────────────
    if has_audio and reg_a:
        a_chain = ",".join(reg_a)
        filter_complex = f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
        ])
    else:
        filter_complex = f"[0:v]{v_chain}[v]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
        ])
        if has_audio:
            cmd.extend([
                "-map", "0:a:0",
                "-c:a", "aac",
                "-b:a", AUDIO_BITRATE,
            ])

    # ─────────────────────────────────────────────
    # NVENC encode
    # ─────────────────────────────────────────────
    cmd.extend([
        "-c:v", "h264_nvenc",
        "-preset", "p7",
        "-tune", "hq",
        "-rc", "vbr",
        "-cq", str(CQ_QUALITY),
        "-b:v", "0",
        "-maxrate", "20M",
        "-bufsize", "40M",
        "-profile:v", "high",
        "-level", "4.2",
        "-spatial_aq", "1",
        "-temporal_aq", "1",
        "-rc-lookahead", "32",
        "-surfaces", "64",
        "-movflags", "+faststart",
        "-fps_mode", "passthrough",
    ])

    # Only force pix_fmt if we touched CPU
    if is_hybrid:
        cmd.extend(["-pix_fmt", "yuv420p"])
    else:
        # Pure GPU path: ensure we output something NVENC likes if it's not already cuda
        # But since we use -hwaccel_output_format cuda, it's already cuda.
        pass

    cmd.append(temp_out)

    run_ffmpeg(cmd, timeout=MAX_SEGMENT_TIMEOUT)
    return temp_out


def _build_gpu_filter_chain(
    seg,
    out_w,
    out_h,
    orig_w,
    orig_h,
    has_audio,
    debug_overlay,
    seg_idx,
    reg_v,
):
    """
    Safe GPU ↔ CPU filter chain for rendering segments.

    Rules:
    - GPU filters only receive CUDA frames
    - CPU filters only receive system memory frames
    - Handles scaling, effects, and debug overlay safely
    """

    gpu_filters: list[str] = []
    needs_cpu = requires_cpu_filters(reg_v, debug_overlay)

    # ----------------------------
    # HYBRID: GPU → CPU → GPU
    # ----------------------------
    if needs_cpu:
        # Download frames to CPU
        gpu_filters.append("hwdownload")  # CUDA → CPU
        gpu_filters.append("format=nv12")  # CPU filters need standard format

        # CPU scaling if resolution changed
        if out_w != orig_w or out_h != orig_h:
            gpu_filters.append(f"scale={out_w}:{out_h}:flags=lanczos")

        # Apply CPU-only video effects
        gpu_filters.extend(reg_v)

        # Debug overlay (optional)
        if debug_overlay:
            text = escape_filter_text(f"[{seg_idx}]")
            gpu_filters.append(
                f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:"
                "box=1:boxcolor=black@0.7:x=10:y=10"
            )

        # Final CPU formatting before sending back to GPU
        gpu_filters.append("setsar=1")
        gpu_filters.append("format=yuv420p")

        # Upload back to GPU for NVENC
        gpu_filters.append("hwupload_cuda")
        return gpu_filters

    # ----------------------------
    # PURE GPU: everything stays on GPU
    # ----------------------------
    # Force a CUDA-compatible input format first
    gpu_filters.append("format=nv12")       # Safe for scale_cuda / scale_npp
    gpu_filters.append("hwupload_cuda")     # Upload to GPU

    # GPU scaling if resolution changed
    if out_w != orig_w or out_h != orig_h:
        scale_filter = "scale_cuda" if USE_SCALE_CUDA else "scale_npp"
        gpu_filters.append(f"{scale_filter}={out_w}:{out_h}:interp_algo={GPU_SCALE_ALGO}")

    # Apply pure GPU filters (must be GPU compatible)
    gpu_filters.extend(reg_v)

    # Debug overlay not allowed here (would need CPU)
    if debug_overlay:
        print(f"⚠️  Warning: debug overlay requires CPU, skipping for segment {seg_idx}")

    # Ensure SAR is set for NVENC
    gpu_filters.append("setsar=1")

    return gpu_filters


def requires_cpu_filters(video_filters: list[str], debug_overlay: bool) -> bool:
    """
    Determine if ANY filter requires CPU frames.
    This prevents illegal CUDA → CPU auto-conversions.
    """
    CPU_FILTER_KEYWORDS = (
        "drawtext",
        "crop=",
        "scale=",
        "subtitles",
        "setpts",
        "setsar",
        "format=",
        "eq",
        "curves",
        "color",
        "hue",
        "lut",
    )

    if debug_overlay:
        return True

    for f in video_filters:
        for kw in CPU_FILTER_KEYWORDS:
            if kw in f:
                return True

    return False


def _render_cpu_fallback(args, temp_out):
    """CPU fallback when GPU is unavailable."""
    (i, seg, input_path, temp_dir, fps, debug_overlay, has_audio,
     orig_w, orig_h, out_w, out_h) = args
    
    cmd = [FFMPEG_BIN, "-y", "-ss", str(seg.start), "-t", str(seg.duration), 
           "-i", input_path]
    
    v_filters = []
    if out_w != orig_w or out_h != orig_h:
        v_filters.append(f"scale={out_w}:{out_h}:flags=fast_bilinear")
    
    reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
    v_filters.extend(reg_v)
    
    if debug_overlay:
        text = escape_filter_text(f"[{i}]")
        v_filters.append(
            f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:"
            f"box=1:boxcolor=black@0.7:x=10:y=10"
        )
    
    v_filters.append("setsar=1")
    v_filters.append("format=yuv420p")
    
    if reg_a and has_audio:
        filter_complex = f"[0:v]{','.join(v_filters)}[v];[0:a]{','.join(reg_a)}[a]"
        cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
    else:
        cmd.extend(["-vf", ",".join(v_filters)])
        if has_audio:
            cmd.extend(["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", AUDIO_BITRATE])
    
    cmd.extend([
        "-c:v", "libx264",
        "-preset", ENCODING_PRESET,
        "-crf", str(CRF_QUALITY),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-vsync", "cfr",
        temp_out
    ])
    
    run_ffmpeg(cmd, timeout=MAX_SEGMENT_TIMEOUT)
    return temp_out