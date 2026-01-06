import json
import subprocess
from typing import Dict, Any, Tuple
from config import FFPROBE_BIN, RESOLUTION_PRESETS

def get_output_resolution(original_width: int, original_height: int, 
                          requested_res: str = "720p") -> Tuple[int, int]:
    """Get target output resolution dynamically."""
    if requested_res == "original" or requested_res not in RESOLUTION_PRESETS:
        return original_width, original_height
    
    target = RESOLUTION_PRESETS[requested_res]
    return target if target else (original_width, original_height)

def get_video_info(path: str) -> Dict[str, Any]:
    """Get video metadata efficiently."""
    cmd = [
        FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,codec_type,width,height,duration,r_frame_rate:format=duration",
        "-of", "json", path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    
    streams = data.get("streams", [])
    format_info = data.get("format", {})
    v_stream = streams[0] if streams else {}
    
    duration = float(v_stream.get("duration", format_info.get("duration", 0)))
    r_frame_rate = v_stream.get("r_frame_rate", "30/1")
    num, den = map(int, r_frame_rate.split('/'))
    fps = num / den if den != 0 else 30.0
    
    cmd_audio = [FFPROBE_BIN, "-v", "error", "-select_streams", "a:0", 
                 "-show_entries", "stream=codec_type", "-of", "json", path]
    result_audio = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=10)
    has_audio = bool(json.loads(result_audio.stdout).get("streams"))
    
    return {
        "fps": fps,
        "duration": duration,
        "has_audio": has_audio,
        "width": int(v_stream.get("width", 1920)),
        "height": int(v_stream.get("height", 1080)),
        "codec": v_stream.get("codec_name", "unknown")
    }
