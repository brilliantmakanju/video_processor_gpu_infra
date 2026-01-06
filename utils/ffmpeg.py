import os
import signal
import subprocess
from typing import List

def run_ffmpeg(args: List[str], timeout: int = 300) -> None:
    """Run FFmpeg with timeout."""
    env = os.environ.copy()
    
    if "-loglevel" not in args:
        args.insert(1, "-loglevel")
        args.insert(2, "error")
    
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode != 0:
            error_msg = stderr[-1000:] if stderr else "Unknown error"
            raise RuntimeError(f"FFmpeg failed: {error_msg}")
                
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()
        process.wait()
        raise RuntimeError(f"FFmpeg timeout after {timeout}s")
    except Exception as e:
        raise RuntimeError(f"FFmpeg error: {str(e)}")
