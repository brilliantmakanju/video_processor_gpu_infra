#!/usr/bin/env python3
import os
import time
import runpod
from config import *
from models import *
from utils.logging import log
from storage.r2 import upload_to_r2
from storage.gofile import upload_to_gofile
from storage.downloader import download_file
from processor.analyzer import parse_edit_map
from processor.timeline import create_segments
# from effects.caption import cleanup_subtitle_files
from processor.final_renderer import render_final_video
from utils.video import get_video_info, get_output_resolution
from processor.job_parser import parse_job_input, load_edit_data
from effects.watermark import apply_watermark, download_watermark, cleanup_watermark

import signal

def handler(job):
    """Main RunPod handler with Global Timeout and Robust Error Handling."""
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Global job timeout reached (2 hours)")

    # Set global timeout of 2 hours (7200 seconds)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(7200)

    try:
        if not job or 'input' not in job:
            raise ValueError("Invalid job format: missing 'input' field")

        v_url, e_url, u_url, p_url, o_res, is_paid = parse_job_input(job['input'])
        print(f"DEBUG: Job Input - Video: {v_url}, Edits: {e_url}, Res: {o_res}, Paid: {is_paid}")

        log(f"Downloading files (Target: {o_res}, Paid: {is_paid})...")
        download_file(v_url, INPUT_VIDEO, 8192, 300) # Increased timeout for large videos
        edit_data = load_edit_data(e_url)
        print(f"DEBUG: Downloaded video size: {os.path.getsize(INPUT_VIDEO)} bytes")
        
        info = get_video_info(INPUT_VIDEO)
        print(f"DEBUG: Video Info - {info}")
        edits, subtitles = parse_edit_map(edit_data)
        out_w, out_h = get_output_resolution(info["width"], info["height"], o_res)
        segments = create_segments(edits, subtitles, info["duration"], info["width"], info["height"], out_w, out_h)
        print(f"DEBUG: Created {len(segments)} segments")
        
        if not segments:
            raise ValueError("No valid segments to process after parsing edit map")

        log(f"Processing {len(segments)} segments at {out_w}x{out_h}...")
        start_time = time.time()

        # Render video (with or without watermark step)
        temp_output = "temp_no_watermark.mp4" if not is_paid and WATERMARK_URL else OUTPUT_VIDEO
        render_final_video(segments, INPUT_VIDEO, temp_output)
        
        # Apply watermark for free users
        if not is_paid and WATERMARK_URL:
            log("Applying watermark for free user...")
            wm_path = download_watermark(WATERMARK_URL)
            if wm_path and apply_watermark(temp_output, OUTPUT_VIDEO, out_w, out_h, wm_path):
                log("Watermark applied successfully")
                if os.path.exists(temp_output): os.remove(temp_output)
            else:
                log("Watermark failed or skipped, using unwatermarked video")
                if os.path.exists(temp_output): os.rename(temp_output, OUTPUT_VIDEO)
            cleanup_watermark()
        
        elapsed = time.time() - start_time

        res_url = p_url if u_url else None
        if u_url: 
            upload_to_r2(OUTPUT_VIDEO, u_url)
        elif not p_url: 
            gofile_res = upload_to_gofile(OUTPUT_VIDEO, job['input'].get("gofile_token"))
            if "error" in gofile_res:
                raise RuntimeError(f"Gofile upload failed: {gofile_res['error']}")
            res_url = gofile_res.get("download_url")

        
        return {
            "success": True, 
            "download_url": res_url, 
            "processing_time": round(elapsed, 2), 
            "output_size_mb": round(os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024), 2)
        }
    except TimeoutError as te:
        log(f"Timeout Error: {str(te)}")
        return {"error": "timeout", "message": str(te)}
    except Exception as e:
        log(f"Error: {str(e)}")
        return {"error": "failure", "message": str(e)}
    finally:
        # Disable alarm
        signal.alarm(0)
        # Cleanup
        for f in [INPUT_VIDEO, OUTPUT_VIDEO, "edit_map.json", "temp_no_watermark.mp4"]:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass
        # cleanup_subtitle_files() 
        cleanup_watermark()

runpod.serverless.start({"handler": handler})