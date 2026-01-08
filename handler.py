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
        if not o_res:
            o_res = "original" # Default to original to save space
        print(f"DEBUG: Job Input - Video: {v_url}, Edits: {e_url}, Res: {o_res}, Paid: {is_paid}")

        log(f"Downloading files (Target: {o_res}, Paid: {is_paid})...")
        download_file(v_url, INPUT_VIDEO, 8192, 300) 
        edit_data = load_edit_data(e_url)
        
        # 🔑 SPACE OPTIMIZATION: If file is huge and disk is tight, compress it first
        import shutil
        import os
        from utils.video import compress_video_gpu
        
        file_size_gb = os.path.getsize(INPUT_VIDEO) / (1024**3)
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        
        # If file > 500MB and free space < 5GB, compress it
        if file_size_gb > 0.5 and free_gb < 5.0:
            log(f"⚠️ Low disk space ({free_gb:.1f}GB). Compressing input video to save space...")
            temp_compressed = INPUT_VIDEO + ".tmp.mp4"
            compress_video_gpu(INPUT_VIDEO, temp_compressed, target_bitrate="4M")
            
            if os.path.exists(temp_compressed):
                new_size = os.path.getsize(temp_compressed) / (1024**3)
                log(f"✓ Compressed input from {file_size_gb:.2f}GB to {new_size:.2f}GB")
                os.replace(temp_compressed, INPUT_VIDEO)
            else:
                log("❌ Compression failed, proceeding with original file.")

        info = get_video_info(INPUT_VIDEO)
        print(f"DEBUG: Video Info - {info}")
        edits, subtitles = parse_edit_map(edit_data)
        out_w, out_h = get_output_resolution(info["width"], info["height"], o_res)
        segments = create_segments(edits, subtitles, info["duration"], info["width"], info["height"], out_w, out_h)
        print(f"DEBUG: Created {len(segments)} segments")
        
        if not segments:
            raise ValueError("No valid segments to process after parsing edit map")

        log(f"Processing {len(segments)} segments at {out_w}x{out_h}...")
        
        # Check disk space
        import shutil
        total, used, free = shutil.disk_usage("/")
        log(f"Disk Space: {free // (1024**3)}GB free of {total // (1024**3)}GB")
        if free < 2 * 1024**3: # Less than 2GB
            log("⚠️ WARNING: Low disk space! Processing might fail for large videos.")

        start_time = time.time()

        # Render video (with or without watermark step)
        temp_output = "temp_no_watermark.mp4" if not is_paid and WATERMARK_URL else OUTPUT_VIDEO
        render_final_video(segments, INPUT_VIDEO, temp_output, o_res)
        
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