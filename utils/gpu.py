import subprocess
from config import ENABLE_GPU, GPU_ENCODER, FFMPEG_BIN

_GPU_SUPPORT_CACHE = None

def check_gpu_support() -> bool:
    """Check if the configured GPU encoder is actually usable."""
    global _GPU_SUPPORT_CACHE
    if not ENABLE_GPU:
        return False
    
    if _GPU_SUPPORT_CACHE is not None:
        return _GPU_SUPPORT_CACHE
        
    try:
        cmd_check = [FFMPEG_BIN, "-encoders"]
        result = subprocess.run(cmd_check, capture_output=True, text=True, timeout=5)
        if GPU_ENCODER not in result.stdout:
            _GPU_SUPPORT_CACHE = False
            return False
            
        dummy_cmd = [
            FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", GPU_ENCODER, "-f", "null", "-"
        ]
        process = subprocess.run(dummy_cmd, capture_output=True, text=True, timeout=10)
        _GPU_SUPPORT_CACHE = (process.returncode == 0)
        
        return _GPU_SUPPORT_CACHE
    except Exception:
        _GPU_SUPPORT_CACHE = False
        return False
