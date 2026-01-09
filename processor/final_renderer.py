import os
import shutil
import time
from config import *
from typing import List
from models import Segment
from utils.ffmpeg import run_ffmpeg
from processor.segment_renderer import render_segment_smart
from utils.video import get_video_info, get_output_resolution
from utils.gpu import (
    check_gpu_support, 
    get_gpu_info, 
    monitor_gpu_usage,
    print_gpu_status,
    get_gpu_compute_capability
)
from concurrent.futures import ThreadPoolExecutor
from effects.watermark import download_watermark, cleanup_watermark

def render_final_video(segments: List[Segment], input_path: str, output_path: str, 
                       output_res: str = "original", is_paid: bool = True):
    """
    GPU-optimized final video rendering.
    Processes segments in parallel for maximum throughput.
    """
    temp_dir = "temp_spliceo_v2"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Print GPU status
    print("\n" + "="*60)
    print("GPU STATUS")
    print("="*60)
    print_gpu_status()
    
    if not check_gpu_support():
        print("⚠️  WARNING: GPU not available, falling back to CPU encoding")
    else:
        print("✓ GPU acceleration enabled")
        gpu_info = get_gpu_info()
        if gpu_info:
            print(f"✓ Available VRAM: {gpu_info['free_memory_mb']} MB")
    
    print("="*60 + "\n")
    
    # Get video info
    info = get_video_info(input_path)
    orig_w, orig_h = info["width"], info["height"]
    out_w, out_h = get_output_resolution(orig_w, orig_h, output_res)
    
    # If final pass is enabled, render segments at original resolution
    render_w, render_h = (orig_w, orig_h) if FINAL_UP_COMPRESS else (out_w, out_h)
    
    print(f"Input: {orig_w}x{orig_h} @ {info['fps']}fps")
    print(f"Output: {out_w}x{out_h}")
    print(f"Segments: {len(segments)}")
    print(f"Total duration: {sum(s.duration for s in segments):.2f}s\n")
    
    # Download watermark once if needed
    watermark_path = None
    if not is_paid and WATERMARK_URL:
        print("Downloading watermark for integrated rendering...")
        watermark_path = download_watermark(WATERMARK_URL)

    # Prepare render arguments
    render_args = [
        (i, seg, input_path, temp_dir, info["fps"], DEBUG_OVERLAY, info["has_audio"],
         orig_w, orig_h, render_w, render_h, is_paid, watermark_path)
        for i, seg in enumerate(segments)
    ]
    
    segment_files = []
    start_time = time.time()
    
    try:
        # Process segments in parallel
        print(f"Processing {len(segments)} segments in parallel (Max workers: {MAX_PARALLEL_SEGMENTS})...")
        
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SEGMENTS) as executor:
            # Map the render function to the arguments
            # We use a wrapper to handle the index and result
            results = list(executor.map(render_segment_smart, render_args))
            
            for i, segment_file in enumerate(results):
                segment_files.append((i, segment_file))
        
        processing_time = time.time() - start_time
        print(f"\n✓ All segments processed in {processing_time:.1f}s")
        print(f"  Average: {processing_time/len(segments):.1f}s per segment\n")
        
        # 🔑 SPACE OPTIMIZATION: Delete input video before concatenation
        # We don't need it anymore as all segments are rendered.
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
                print(f"✓ Deleted input video to free up space ({os.path.basename(input_path)})")
            except Exception as e:
                print(f"⚠️  Failed to delete input video: {e}")

        # Concatenate segments
        print("Concatenating segments...")
        concat_start = time.time()
        
        segment_files.sort(key=lambda x: x[0])
        concat_list = os.path.join(temp_dir, "concat.txt")
        
        with open(concat_list, "w") as f:
            for _, sf in segment_files:
                f.write(f"file '{os.path.abspath(sf)}'\n")
        
        # Use copy mode for concatenation (no re-encoding)
        # This is nearly instant and preserves the quality of rendered segments
        final_cmd = [
            FFMPEG_BIN, "-y",
            "-f", "concat",
            "-safe", "0",
            "-fflags", "+genpts",
            "-i", concat_list,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path
        ]
        
        run_ffmpeg(final_cmd, timeout=MAX_CONCAT_TIMEOUT)
        
        concat_time = time.time() - concat_start
        total_time = time.time() - start_time
        
        # Final statistics
        output_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        
        print(f"\n{'='*60}")
        print("PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Concatenation time: {concat_time:.1f}s")
        print(f"Total time: {total_time:.1f}s")
        print(f"Output size: {output_size:.1f} MB")
        print(f"Output path: {output_path}")
        
        if ENABLE_GPU_MONITORING:
            final_usage = monitor_gpu_usage()
            if final_usage:
                print(f"\nFinal GPU state:")
                print(f"  VRAM used: {final_usage['memory_used_mb']} MB")
                print(f"  GPU utilization: {final_usage['gpu_util']}%")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        raise
    finally:
        # Cleanup temp directory
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print("✓ Cleaned up temporary files")
            except Exception as e:
                print(f"⚠️  Failed to cleanup temp directory: {e}")


def estimate_processing_time(segments: List[Segment], input_path: str) -> float:
    """
    Estimate processing time based on GPU capabilities and video properties.
    Returns estimated time in seconds.
    """
    info = get_video_info(input_path)
    total_duration = sum(s.duration for s in segments)
    
    gpu_info = get_gpu_info()
    
    if not gpu_info:
        # CPU fallback: roughly real-time to 2x speed
        return total_duration * 0.5
    
    # GPU processing estimates (RTX 5090):
    # - Simple segments (copy mode): ~0.01x duration
    # - With effects: ~0.05-0.1x duration
    # - Heavy effects: ~0.2x duration
    
    copy_segments = sum(1 for s in segments if s.can_copy)
    effect_segments = len(segments) - copy_segments
    
    copy_time = copy_segments * 0.5  # Very fast
    effect_time = effect_segments * total_duration * 0.08  # ~12x realtime
    
    return copy_time + effect_time + 5  # Add 5s for overhead


def validate_gpu_setup():
    """Validate GPU setup before processing."""
    print("\nValidating GPU setup...")
    
    if not check_gpu_support():
        print("❌ GPU validation failed")
        return False
    
    gpu_info = get_gpu_info()
    if not gpu_info:
        print("❌ Could not retrieve GPU information")
        return False
    
    print(f"✓ GPU detected: {gpu_info['name']}")
    print(f"✓ Compute capability: {gpu_info['compute_capability']}")
    print(f"✓ Total VRAM: {gpu_info['total_memory_mb']} MB")
    print(f"✓ Available VRAM: {gpu_info['free_memory_mb']} MB")
    
    # Check minimum VRAM (4GB minimum recommended)
    if gpu_info['free_memory_mb'] < 4000:
        print("⚠️  Warning: Less than 4GB VRAM available")
        print("   Processing may be slow or fail for large videos")
    
    return True