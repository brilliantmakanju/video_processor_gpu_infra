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
from processor.final_renderer import render_final_video
from utils.video import get_video_info, get_output_resolution
from processor.job_parser import parse_job_input, load_edit_data
from effects.watermark import apply_watermark, download_watermark, cleanup_watermark

def handler(job):
    """Main RunPod handler - Simplified with Dynamic Resolution."""
    try:
        v_url, e_url, u_url, p_url, o_res, is_paid = parse_job_input(job['input'])

        log(f"Downloading files (Target: {o_res}, Paid: {is_paid})...")
        download_file(v_url, INPUT_VIDEO, 8192, 120)
        edit_data = load_edit_data(e_url)
        
        info = get_video_info(INPUT_VIDEO)
        edits, subtitles = parse_edit_map(edit_data)
        out_w, out_h = get_output_resolution(info["width"], info["height"], o_res)
        segments = create_segments(edits, subtitles, info["duration"], info["width"], info["height"], out_w, out_h)
        
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
                os.remove(temp_output)
            else:
                log("Watermark failed, using unwatermarked video")
                os.rename(temp_output, OUTPUT_VIDEO)
            cleanup_watermark()
        
        elapsed = time.time() - start_time

        res_url = p_url if u_url else None
        if u_url: upload_to_r2(OUTPUT_VIDEO, u_url)
        elif not p_url: res_url = upload_to_gofile(OUTPUT_VIDEO, job['input'].get("gofile_token")).get("download_url")
        
        return {"success": True, "download_url": res_url, "processing_time": elapsed, "output_size_mb": os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)}
    except Exception as e:
        log(f"Error: {str(e)}")
        return {"error": str(e)}
    finally:
        for f in [INPUT_VIDEO, OUTPUT_VIDEO, "edit_map.json", "temp_no_watermark.mp4"]:
            if os.path.exists(f): os.remove(f)
        cleanup_watermark()

runpod.serverless.start({"handler": handler})