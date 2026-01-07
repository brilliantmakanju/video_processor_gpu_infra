import os
from config import *
from typing import Tuple
from models import Segment
from utils.ffmpeg import run_ffmpeg
from utils.gpu import check_gpu_support
from utils.text import escape_filter_text
from effects.registry import get_segment_filters

def render_segment_smart(args: Tuple) -> str:
    """Ultra-optimized segment rendering using effect registry."""
    (i, seg, input_path, temp_dir, fps, debug_overlay, has_audio,
     orig_w, orig_h, out_w, out_h) = args
    
    temp_out = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
    
    if seg.can_copy and SMART_COPY_MODE:
        cmd = [FFMPEG_BIN, "-y", "-ss", str(seg.start), "-t", str(seg.duration),
               "-i", input_path, "-c", "copy", "-avoid_negative_ts", "make_zero", temp_out]
        run_ffmpeg(cmd)
        return temp_out
    
    v_filters = []
    if out_w != orig_w or out_h != orig_h:
        v_filters.append(f"scale={out_w}:{out_h}:flags=fast_bilinear")
    
    # Get filters from registry
    reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
    v_filters.extend(reg_v)
    
    if debug_overlay:
        text = escape_filter_text(f"[{i}]")
        v_filters.append(f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:box=1:boxcolor=black@0.7:x=10:y=10")
    
    # Force square SAR and consistent pixel format to ensure concat compatibility
    v_filters.append("setsar=1")
    v_filters.append("format=yuv420p")
    
    cmd = [FFMPEG_BIN, "-y", "-ss", str(seg.start), "-t", str(seg.duration), "-i", input_path]
    
    if reg_a and has_audio:
        filter_complex = f"[0:v]{','.join(v_filters)}[v];[0:a]{','.join(reg_a)}[a]"
        cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
    else:
        cmd.extend(["-vf", ",".join(v_filters)])
        if has_audio: cmd.extend(["-c:a", "aac", "-b:a", AUDIO_BITRATE])
    
    use_gpu = check_gpu_support()
    if use_gpu:
        cmd.extend(["-c:v", GPU_ENCODER, "-preset", GPU_PRESET, "-rc", "vbr", "-cq", str(CQ_QUALITY), "-pix_fmt", "yuv420p"])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", ENCODING_PRESET, "-crf", str(CRF_QUALITY), "-pix_fmt", "yuv420p"])
    
    cmd.extend(["-movflags", "+faststart", temp_out])
    run_ffmpeg(cmd, timeout=MAX_SEGMENT_TIMEOUT)
    return temp_out
