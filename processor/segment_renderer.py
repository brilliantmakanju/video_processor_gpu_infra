import os
from config import *
from typing import Tuple
from models import Segment
from utils.ffmpeg import run_ffmpeg
from utils.gpu import check_gpu_support, get_gpu_compute_capability
from utils.text import escape_filter_text
from effects.registry import get_segment_filters

def render_segment_smart(args: Tuple) -> str:
    """Ultra-optimized segment rendering with full GPU acceleration."""
    (i, seg, input_path, temp_dir, fps, debug_overlay, has_audio,
     orig_w, orig_h, out_w, out_h) = args
    
    temp_out = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
    
    # Smart copy mode for segments without effects
    if seg.can_copy and SMART_COPY_MODE:
        cmd = [FFMPEG_BIN, "-y", "-ss", str(seg.start), "-t", str(seg.duration),
               "-i", input_path, "-c", "copy", "-avoid_negative_ts", "make_zero", temp_out]
        run_ffmpeg(cmd)
        return temp_out
    
    use_gpu = check_gpu_support()
    
    if not use_gpu:
        return _render_cpu_fallback(args, temp_out)
    
    # Full GPU pipeline
    cmd = [FFMPEG_BIN, "-y"]
    
    # GPU decoding with NVDEC
    cmd.extend([
        "-vsync", "0",  # Critical for hardware acceleration
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",  # Keep frames in GPU memory
        "-hwaccel_device", "0",  # Use first GPU
        "-extra_hw_frames", "8",  # Buffer for async processing
    ])
    
    cmd.extend(["-ss", str(seg.start), "-t", str(seg.duration), "-i", input_path])
    
    # Build GPU filter chain
    gpu_filters = _build_gpu_filter_chain(
        seg, out_w, out_h, orig_w, orig_h, has_audio, debug_overlay, i
    )
    
    # Apply filters
    reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
    
    if reg_a and has_audio:
        # Complex filter with audio
        v_chain = ",".join(gpu_filters)
        a_chain = ",".join(reg_a)
        filter_complex = f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]"
        cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
        cmd.extend(["-c:a", "aac", "-b:a", AUDIO_BITRATE])
    else:
        # Video only
        cmd.extend(["-vf", ",".join(gpu_filters)])
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", AUDIO_BITRATE])
    
    # GPU encoding with NVENC - optimized for RTX 5090
    cmd.extend([
        "-c:v", "h264_nvenc",
        "-preset", "p7",  # Highest quality preset
        "-tune", "hq",  # High quality tuning
        "-rc", "vbr",  # Variable bitrate
        "-cq", str(CQ_QUALITY),  # Constant quality (lower = better, 19-23 recommended)
        "-b:v", "0",  # Let encoder decide bitrate
        "-maxrate", "20M",  # Cap max bitrate
        "-bufsize", "40M",  # 2x maxrate for VBR
        "-profile:v", "high",
        "-level", "4.2",
        "-pix_fmt", "yuv420p",
        "-spatial_aq", "1",  # Spatial adaptive quantization
        "-temporal_aq", "1",  # Temporal adaptive quantization
        "-rc-lookahead", "32",  # Look ahead frames for better quality
        "-surfaces", "64",  # Maximize GPU utilization
        "-movflags", "+faststart",
        "-fps_mode", "passthrough",  # Preserve frame timing
        temp_out
    ])
    
    run_ffmpeg(cmd, timeout=MAX_SEGMENT_TIMEOUT)
    return temp_out


def _build_gpu_filter_chain(seg, out_w, out_h, orig_w, orig_h, has_audio, 
                            debug_overlay, seg_idx):
    """Build optimized GPU filter chain."""
    gpu_filters = []
    needs_cpu_filters = False
    
    # Get effect filters
    reg_v, _ = get_segment_filters(seg, out_w, out_h, has_audio)
    
    # Check if we need CPU processing
    needs_cpu_filters = bool(reg_v) or debug_overlay
    
    # Scaling with GPU (scale_cuda is much faster than scale_npp)
    if out_w != orig_w or out_h != orig_h:
        # Use scale_cuda for better performance
        gpu_filters.append(f"scale_cuda={out_w}:{out_h}:interp_algo=lanczos")
    
    # If we have software filters, we need to download from GPU
    if needs_cpu_filters:
        gpu_filters.append("hwdownload")
        gpu_filters.append("format=nv12")
        
        # Add software filters
        if reg_v:
            gpu_filters.extend(reg_v)
        
        # Debug overlay
        if debug_overlay:
            text = escape_filter_text(f"[{seg_idx}]")
            gpu_filters.append(
                f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:"
                f"box=1:boxcolor=black@0.7:x=10:y=10"
            )
        
        # Upload back to GPU
        gpu_filters.append("hwupload_cuda")
    
    # Final pixel format and SAR
    gpu_filters.append("scale_cuda=format=yuv420p")
    gpu_filters.append("setsar=1")
    
    return gpu_filters


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