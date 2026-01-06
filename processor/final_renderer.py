import os
import shutil
from config import *
from typing import List
from models import Segment
from utils.ffmpeg import run_ffmpeg
from concurrent.futures import ProcessPoolExecutor
from processor.segment_renderer import render_segment_smart
from utils.video import get_video_info, get_output_resolution

def render_final_video(segments: List[Segment], input_path: str, output_path: str):
    """Optimized final rendering."""
    temp_dir = "temp_spliceo_v2"
    os.makedirs(temp_dir, exist_ok=True)
    
    info = get_video_info(input_path)
    orig_w, orig_h = info["width"], info["height"]
    out_w, out_h = get_output_resolution(orig_w, orig_h)
    
    render_args = [
        (i, seg, input_path, temp_dir, info["fps"], DEBUG_OVERLAY, info["has_audio"],
         orig_w, orig_h, out_w, out_h)
        for i, seg in enumerate(segments)
    ]
    
    segment_files = []
    try:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(render_segment_smart, arg): i for i, arg in enumerate(render_args)}
            for future in futures:
                segment_files.append((futures[future], future.result()))
        
        segment_files.sort(key=lambda x: x[0])
        concat_list = os.path.join(temp_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for _, sf in segment_files:
                f.write(f"file '{os.path.abspath(sf)}'\n")
        
        final_cmd = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", "-movflags", "+faststart", output_path]
        run_ffmpeg(final_cmd, timeout=600)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
