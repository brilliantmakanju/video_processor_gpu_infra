import os
from config import (
    FFMPEG_BIN, SMART_COPY_MODE, AUDIO_BITRATE, CQ_QUALITY, 
    MAX_SEGMENT_TIMEOUT, USE_SCALE_CUDA, GPU_SCALE_ALGO,
    DECODER_THREADS, DECODER_SURFACES
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
    # Collect filters and determine pipeline type
    # ─────────────────────────────────────────────
    reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
    needs_cpu = requires_cpu_filters(reg_v, debug_overlay)

    # ─────────────────────────────────────────────
    # Base FFmpeg command
    # ─────────────────────────────────────────────
    cmd = [
        FFMPEG_BIN, "-y",
        "-hwaccel", "cuda",
    ]

    # 🔑 KEY FIX: For hybrid paths, force decoder to output NV12 (system memory).
    # For pure GPU paths, force decoder to output CUDA (GPU memory).
    if needs_cpu:
        cmd.extend(["-hwaccel_output_format", "nv12"])
    else:
        cmd.extend(["-hwaccel_output_format", "cuda"])

    cmd.extend([
        "-hwaccel_device", "0",
        "-extra_hw_frames", "8",
        "-threads", str(DECODER_THREADS),
        "-ss", str(seg.start),
        "-t", str(seg.duration),
        "-i", input_path,
    ])

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

    is_hybrid = needs_cpu

    v_chain = ",".join(gpu_filters)

    # ─────────────────────────────────────────────
    # ALWAYS use filter_complex (NO -vf)
    # ─────────────────────────────────────────────
    if has_audio and reg_a:
        a_chain = ",".join(reg_a)
        filter_complex = f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]"
        print(f"DEBUG: Filter Complex (with audio): {filter_complex}")
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
        ])
    else:
        filter_complex = f"[0:v]{v_chain}[v]"
        print(f"DEBUG: Filter Complex (video only): {filter_complex}")
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
        "-spatial_aq", "1",
        "-temporal_aq", "1",
        "-rc-lookahead", "32",
        "-surfaces", "32", # Reduced from 64 for stability
        "-movflags", "+faststart",
        "-fps_mode", "passthrough",
    ])

    # 🔑 CRITICAL: Never use -pix_fmt yuv420p with NVENC if we are feeding it CUDA frames.
    # NVENC handles the pixel format natively on the GPU.
    # if is_hybrid:
    #     cmd.extend(["-pix_fmt", "yuv420p"])

    cmd.append(temp_out)

    print(f"DEBUG: Running FFmpeg command for segment {i}:")
    print(f"DEBUG: {' '.join(cmd)}")
    
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

    if needs_cpu:
        # ----------------------------
        # HYBRID: GPU → CPU → GPU
        # ----------------------------
        # 🔑 We OMITTED -hwaccel_output_format cuda in the command,
        # so frames arrive here in system memory (NV12 or similar).
        # NO hwdownload needed!
        gpu_filters.append("format=nv12")  # Ensure consistent CPU format

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
        
        print(f"DEBUG: Hybrid Filter Chain for segment {seg_idx}: {gpu_filters}")
        return gpu_filters

    # ----------------------------
    # PURE GPU: everything stays on GPU
    # ----------------------------
    # 🔑 Frames are already in CUDA due to -hwaccel_output_format cuda
    # Adding hwupload_cuda here causes "Impossible to convert" errors.
    gpu_filters.append("format=cuda")

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

    print(f"DEBUG: GPU Filter Chain for segment {seg_idx}: {gpu_filters}")
    return gpu_filters


def requires_cpu_filters(video_filters: list[str], debug_overlay: bool) -> bool:
    """
    Determine if ANY filter requires CPU frames.
    This prevents illegal CUDA → CPU auto-conversions.
    """
    # Filters that are definitely CPU-only
    CPU_ONLY_FILTERS = (
        "drawtext",
        "subtitles",
        "eq",
        "curves",
        "color",
        "hue",
        "lut",
    )

    if debug_overlay:
        return True

    for f in video_filters:
        # Check for CPU-only filters
        for kw in CPU_ONLY_FILTERS:
            if kw in f:
                return True
        
        # Check for software scale/crop/format (avoiding _cuda and _npp)
        if "scale=" in f and "_cuda" not in f and "_npp" not in f:
            return True
        if "crop=" in f and "_cuda" not in f and "_npp" not in f:
            return True
        if "format=" in f and "format=cuda" not in f and "format=nv12" not in f:
            # Note: format=nv12 is used in hybrid path, but here we check if it's in reg_v
            return True
        if "setpts" in f: # setpts is usually CPU, though there might be GPU variants
            return True
        if "setsar" in f:
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