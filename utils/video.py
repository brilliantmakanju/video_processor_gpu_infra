import json
import subprocess
from typing import Dict, Any, Tuple
from config import FFPROBE_BIN, RESOLUTION_PRESETS

class VideoInfoError(RuntimeError):
    """Base error for video inspection failures."""


class VideoTruncatedError(VideoInfoError):
    """File is incomplete — moov atom missing because the file was cut short."""


class VideoCorruptError(VideoInfoError):
    """File exists but ffprobe cannot parse it at all."""

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

def compress_video_gpu(
    input_path: str,
    output_path: str,
    target_bitrate: str = "8M",
    timeout_s: int = 1800,
) -> None:
    """
    Quickly compress a video using GPU to save disk space (pre-processing step).
    Raises RuntimeError if ffmpeg fails or produces an empty file.
    """
    from config import FFMPEG_BIN, GPU_ENCODER

    if not os.path.exists(input_path):
        raise RuntimeError(f"compress_video_gpu: input not found: {input_path}")

    cmd = [
        FFMPEG_BIN, "-y", "-v", "error",
        "-hwaccel", "cuda",
        "-i", input_path,
        "-c:v", GPU_ENCODER,
        "-b:v", target_bitrate,
        "-maxrate", target_bitrate,
        "-bufsize", "2M",
        "-preset", "p4",            # fast but not quality-destroying
        # drop -tune ll — it's for streaming, not compression
        "-tag:v", "hvc1" if "hevc" in GPU_ENCODER else "avc1",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(
        "Compressing %s -> %s (encoder=%s, bitrate=%s)",
        input_path, output_path, GPU_ENCODER, target_bitrate,
    )

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"compress_video_gpu: ffmpeg timed out after {timeout_s}s"
        )

    if result.returncode != 0:
        # THIS is what you were missing — surface the actual failure
        stderr_tail = (result.stderr or "").strip()[-1000:]
        raise RuntimeError(
            f"compress_video_gpu: ffmpeg failed (rc={result.returncode}) "
            f"for {input_path}\n{stderr_tail}"
        )

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(
            f"compress_video_gpu: ffmpeg produced empty output: {output_path}"
        )

    in_mb = os.path.getsize(input_path) / (1024 * 1024)
    out_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(
        "Compression done: %.1f MB -> %.1f MB (%.1f%% saved)",
        in_mb, out_mb, (1 - out_mb / in_mb) * 100 if in_mb else 0,
    )

def get_video_info(path: str) -> Dict[str, Any]:
    """Get video metadata efficiently with robust error handling."""
    try:
        
        if not os.path.exists(path):
            raise VideoInfoError(f"File does not exist: {path}")
        if os.path.getsize(path) == 0:
            raise VideoTruncatedError(f"File is empty (0 bytes): {path}")


        cmd = [
            FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,duration,r_frame_rate"
            ":format=duration",
            "-of", "json", path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "moov atom not found" in stderr:
                raise VideoTruncatedError(
                    f"MP4 missing 'moov' atom — truncated or not a valid MP4 "
                    f"(size={os.path.getsize(path)} bytes): {path}"
                )
          
            if "Invalid data found" in stderr:
                raise VideoCorruptError(f"FFprobe cannot parse file: {stderr}")
            
            raise VideoInfoError(f"FFprobe failed: {stderr}")

        #    raise RuntimeError(f"FFprobe failed: {result.stderr}")
            
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
    except VideoInfoError:
        raise  # already typed — don't re-wrap
    except subprocess.TimeoutExpired as e:
        raise VideoInfoError(f"FFprobe timed out on {path}: {e}") from e
    except Exception as e:
        raise VideoInfoError(f"Failed to get video info for {path}: {e}") from e
  #  except Exception as e:
   #     raise RuntimeError(f"Failed to get video info for {path}: {str(e)}")
