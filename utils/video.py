import json
import subprocess
from typing import Dict, Any, Tuple
from config import FFPROBE_BIN, RESOLUTION_PRESETS

def get_output_resolution(original_width: int, original_height: int, 
                          requested_res: str = "original") -> Tuple[int, int]:
    """
    Get target output resolution dynamically.
    Allows upscaling if requested, but logs a warning.
    """
    if requested_res == "original" or requested_res not in RESOLUTION_PRESETS:
        return original_width, original_height
    
    target_w, target_h = RESOLUTION_PRESETS[requested_res]
    
    if original_width < target_w or original_height < target_h:
        print(f"DEBUG: Upscaling from {original_width}x{original_height} to {requested_res} ({target_w}x{target_h}).")
        
    return target_w, target_h

def compress_video_gpu(input_path: str, output_path: str, target_bitrate: str = "5M"):
    """
    Quickly compress a video using GPU to save disk space.
    Used for pre-processing large input files.
    """
    from config import FFMPEG_BIN, GPU_ENCODER
    cmd = [
        FFMPEG_BIN, "-y",
        "-hwaccel", "cuda",
        "-i", input_path,
        "-c:v", GPU_ENCODER,
        "-b:v", target_bitrate,
        "-preset", "p1", # Fastest possible preset for pre-processing
        "-tune", "ll",   # Low latency
        "-c:a", "copy",   # Keep original audio
        output_path
    ]
    print(f"DEBUG: Compressing input video to save space: {input_path} -> {output_path}")
    subprocess.run(cmd, capture_output=True, text=True)

def get_video_info(path: str) -> Dict[str, Any]:
    """Get video metadata efficiently with robust error handling."""
    try:
        cmd = [
            FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,codec_type,width,height,duration,r_frame_rate:format=duration",
            "-of", "json", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")
            
        data = json.loads(result.stdout)
        
        streams = data.get("streams", [])
        format_info = data.get("format", {})
        v_stream = streams[0] if streams else {}
        
        duration = float(v_stream.get("duration", format_info.get("duration", 0)))
        r_frame_rate = v_stream.get("r_frame_rate", "30/1")
        
        try:
            num, den = map(int, r_frame_rate.split('/'))
            fps = num / den if den != 0 else 30.0
        except (ValueError, ZeroDivisionError):
            fps = 30.0
            
        cmd_audio = [FFPROBE_BIN, "-v", "error", "-select_streams", "a:0", 
                     "-show_entries", "stream=codec_type", "-of", "json", path]
        result_audio = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=10)
        has_audio = False
        if result_audio.returncode == 0:
            try:
                has_audio = bool(json.loads(result_audio.stdout).get("streams"))
            except json.JSONDecodeError:
                pass
        
        return {
            "fps": fps,
            "duration": duration,
            "has_audio": has_audio,
            "width": int(v_stream.get("width", 1920)),
            "height": int(v_stream.get("height", 1080)),
            "codec": v_stream.get("codec_name", "unknown")
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get video info for {path}: {str(e)}")
