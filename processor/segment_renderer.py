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
    
    use_gpu = check_gpu_support()
    
    cmd = [FFMPEG_BIN, "-y"]
    if use_gpu:
        # -vsync 0 is recommended for hardware acceleration
        cmd.extend(["-vsync", "0", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
    
    cmd.extend(["-ss", str(seg.start), "-t", str(seg.duration), "-i", input_path])
    
    # Update filters to use scale_cuda if resizing is needed
    if use_gpu:
        gpu_filters = []
        if out_w != orig_w or out_h != orig_h:
            gpu_filters.append(f"scale_cuda={out_w}:{out_h}")
        
        # Note: Some filters like drawtext might still require downloading to system memory
        # or using specific hardware-accelerated versions if available.
        # For now, we'll keep it simple and use scale_cuda.
        
        reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
        # We might need to handle filter compatibility here if reg_v contains software filters.
        # If reg_v has software filters, we'd need hwdownload -> software filters -> hwupload.
        # To keep it FULL GPU, we'll assume the registry is updated or we'll wrap them.
        
        # Check if any software filters are present or if debug_overlay (drawtext) is needed
        needs_hw_transition = bool(reg_v) or debug_overlay
        
        if needs_hw_transition:
            # If we have software filters, we must download from GPU memory
            gpu_filters.append("hwdownload,format=nv12")
            if reg_v:
                gpu_filters.extend(reg_v)
        
        if debug_overlay:
            text = escape_filter_text(f"[{i}]")
            # drawtext is a software filter
            if not needs_hw_transition: # If we didn't add hwdownload yet for reg_v
                gpu_filters.append("hwdownload,format=nv12")
            gpu_filters.append(f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:box=1:boxcolor=black@0.7:x=10:y=10")
            
        if needs_hw_transition or debug_overlay: # If we downloaded, we need to upload back
            gpu_filters.append("hwupload_cuda")

        gpu_filters.append("setsar=1")
        
        if reg_a and has_audio:
            filter_complex = f"[0:v]{','.join(gpu_filters)}[v];[0:a]{','.join(reg_a)}[a]"
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
        else:
            cmd.extend(["-vf", ",".join(gpu_filters)])
            if has_audio: 
                cmd.extend(["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", AUDIO_BITRATE])
            else:
                cmd.extend(["-map", "0:v:0"])
        
        cmd.extend(["-c:v", GPU_ENCODER, "-preset", GPU_PRESET, "-rc", "vbr", "-cq", str(CQ_QUALITY)])
        cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart", temp_out])
    else:
        # Software fallback
        v_filters = []
        if out_w != orig_w or out_h != orig_h:
            v_filters.append(f"scale={out_w}:{out_h}:flags=fast_bilinear")
        
        reg_v, reg_a = get_segment_filters(seg, out_w, out_h, has_audio)
        v_filters.extend(reg_v)
        
        if debug_overlay:
            text = escape_filter_text(f"[{i}]")
            v_filters.append(f"drawtext=text='{text}':fontcolor=yellow:fontsize=20:box=1:boxcolor=black@0.7:x=10:y=10")
        
        v_filters.append("setsar=1")
        v_filters.append("format=yuv420p")
        
        if reg_a and has_audio:
            filter_complex = f"[0:v]{','.join(v_filters)}[v];[0:a]{','.join(reg_a)}[a]"
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
        else:
            cmd.extend(["-vf", ",".join(v_filters)])
            if has_audio: 
                cmd.extend(["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", AUDIO_BITRATE])
            else:
                cmd.extend(["-map", "0:v:0"])
        
        cmd.extend(["-c:v", "libx264", "-preset", ENCODING_PRESET, "-crf", str(CRF_QUALITY)])
        cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-vsync", "cfr", temp_out])
    
    run_ffmpeg(cmd, timeout=MAX_SEGMENT_TIMEOUT)
    return temp_out
