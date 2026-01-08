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
    """
    Deterministic, GPU-accelerated segment renderer.

    Guarantees:
    - CUDA frames NEVER touch CPU filters
    - CPU filters ALWAYS receive system-memory frames
    - NVENC ALWAYS receives CUDA frames
    """

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

    # 🔑 HYBRID DETECTION
    is_hybrid = "hwdownload" in gpu_filters

    # ─────────────────────────────────────────────
    # Apply filters & mapping
    # ─────────────────────────────────────────────
    if reg_a and has_audio:
        v_chain = ",".join(gpu_filters)
        a_chain = ",".join(reg_a)

        cmd.extend([
            "-filter_complex",
            f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
        ])
    else:
        cmd.extend([
            "-vf", ",".join(gpu_filters),
            "-map", "0:v:0",
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

    # ✅ ONLY force pix_fmt when HYBRID
    if is_hybrid:
        cmd.extend(["-pix_fmt", "yuv420p"])

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
    Build a SAFE filter chain with explicit GPU ↔ CPU boundaries.

    Rules:
    - CUDA frames may ONLY touch GPU filters
    - First CPU filter MUST be preceded by hwdownload
    - Once on CPU, we stay on CPU until hwupload_cuda
    """

    gpu_filters: list[str] = []

    needs_cpu = requires_cpu_filters(reg_v, debug_overlay)

    # ─────────────────────────────────────────────
    # HYBRID PIPELINE (GPU → CPU → GPU)
    # ─────────────────────────────────────────────
    if needs_cpu:
        # 1. Download CUDA frames → system memory
        gpu_filters.append("hwdownload")
        gpu_filters.append("format=nv12")

        # 2. CPU scaling (ONLY here)
        if out_w != orig_w or out_h != orig_h:
            gpu_filters.append(
                f"scale={out_w}:{out_h}:flags=lanczos"
            )

        # 3. CPU-only effects
        for f in reg_v:
            gpu_filters.append(f)

        # 4. Debug overlay (CPU)
        if debug_overlay:
            text = escape_filter_text(f"[{seg_idx}]")
            gpu_filters.append(
                "drawtext="
                f"text='{text}':"
                "fontcolor=yellow:"
                "fontsize=20:"
                "box=1:"
                "boxcolor=black@0.7:"
                "x=10:y=10"
            )

        # 5. Normalize
        gpu_filters.append("setsar=1")
        gpu_filters.append("format=yuv420p")

        # 6. Upload back to GPU for NVENC
        gpu_filters.append("hwupload_cuda")

        return gpu_filters

    # ─────────────────────────────────────────────
    # PURE GPU PIPELINE (NO CPU FILTERS)
    # ─────────────────────────────────────────────
    scale_filter = "scale_cuda" if USE_SCALE_CUDA else "scale_npp"

    if out_w != orig_w or out_h != orig_h:
        gpu_filters.append(
            f"{scale_filter}={out_w}:{out_h}:interp_algo={GPU_SCALE_ALGO}"
        )

    # NOTE:
    # - No setsar
    # - No format
    # - No drawtext
    # - No reg_v allowed here by design

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