import subprocess
from config import ENABLE_GPU, GPU_ENCODER, FFMPEG_BIN

from utils.logging import log

_GPU_SUPPORT_CACHE = None

def check_gpu_support() -> bool:
    """Check if the configured GPU encoder is actually usable."""
    global _GPU_SUPPORT_CACHE
    if not ENABLE_GPU:
        return False
    
    if _GPU_SUPPORT_CACHE is not None:
        return _GPU_SUPPORT_CACHE
        
    try:
        log(f"Checking GPU support for encoder: {GPU_ENCODER}")
        cmd_check = [FFMPEG_BIN, "-encoders"]
        result = subprocess.run(cmd_check, capture_output=True, text=True, timeout=5)
        if GPU_ENCODER not in result.stdout:
            log(f"GPU Encoder {GPU_ENCODER} not found in FFmpeg encoders list.")
            _GPU_SUPPORT_CACHE = False
            return False
            
        log(f"Found {GPU_ENCODER}, running comprehensive hardware acceleration test...")
        # Test both encoder and scale_cuda filter
        dummy_cmd = [
            FFMPEG_BIN, "-y", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-vf", "scale_cuda=128x128",
            "-c:v", GPU_ENCODER, "-f", "null", "-"
        ]
        process = subprocess.run(dummy_cmd, capture_output=True, text=True, timeout=15)
        
        if process.returncode == 0:
            log("GPU hardware acceleration test successful (Encoder + scale_cuda)!")
            _GPU_SUPPORT_CACHE = True
        else:
            log(f"GPU hardware acceleration test failed with return code {process.returncode}")
            log(f"FFmpeg Error: {process.stderr}")
            # Fallback check: maybe just the encoder works but not scale_cuda?
            log("Checking if at least the encoder works...")
            simple_cmd = [
                FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", GPU_ENCODER, "-f", "null", "-"
            ]
            simple_process = subprocess.run(simple_cmd, capture_output=True, text=True, timeout=10)
            if simple_process.returncode == 0:
                log("GPU Encoder works, but full hardware acceleration (scale_cuda) might be missing.")
                # We'll still return True but the renderer will need to be careful.
                # Actually, for "Full GPU", we want this to be True.
                _GPU_SUPPORT_CACHE = True
            else:
                log("GPU Encoder also failed.")
                _GPU_SUPPORT_CACHE = False
        
        return _GPU_SUPPORT_CACHE
    except Exception as e:
        log(f"Exception during GPU check: {str(e)}")
        _GPU_SUPPORT_CACHE = False
        return False
