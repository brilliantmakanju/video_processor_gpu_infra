import os

# ═══════════════════════════════════════════════════════════════
# GPU CONFIGURATION (RTX 5090 Optimized)
# ═══════════════════════════════════════════════════════════════

# Enable GPU acceleration (set to False to force CPU processing)
ENABLE_GPU = True

# GPU encoding settings
GPU_ENCODER = "h264_nvenc"  # NVIDIA hardware encoder
GPU_PRESET = "p7"  # p1-p7, p7 is highest quality
GPU_TUNE = "hq"  # High quality mode
GPU_RC_MODE = "vbr"  # Variable bitrate for better quality
CQ_QUALITY = 19  # Constant quality (lower = better, 18-23 recommended)

# GPU decoder settings
GPU_DECODER = "h264_cuvid"  # NVIDIA hardware decoder
GPU_DECODE_SURFACES = 128  # Max decode surfaces for RTX 5090 (32GB VRAM)

# GPU filter settings
USE_SCALE_CUDA = True  # Use scale_cuda instead of scale_npp (faster)
GPU_SCALE_ALGO = "lanczos"  # Scaling algorithm (lanczos, bicubic, bilinear)

# Advanced NVENC settings
NVENC_SPATIAL_AQ = True  # Spatial adaptive quantization
NVENC_TEMPORAL_AQ = True  # Temporal adaptive quantization
NVENC_RC_LOOKAHEAD = 32  # Frames to look ahead (0-32)
NVENC_SURFACES = 64  # Encoding surfaces (more = better quality but more VRAM)
NVENC_MAXRATE = "20M"  # Maximum bitrate
NVENC_BUFSIZE = "40M"  # Buffer size (2x maxrate recommended)

# ═══════════════════════════════════════════════════════════════
# PROCESSING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# FFmpeg binary path
FFMPEG_BIN = os.environ.get("FFMPEG_PATH", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_PATH", "ffprobe")

INPUT_VIDEO = os.environ.get("INPUT_VIDEO", "input.mp4")
OUTPUT_VIDEO = os.environ.get("OUTPUT_VIDEO", "output.mp4")
EDITMAP_JSON = os.environ.get("EDITMAP_JSON", "editmap.json")

# Smart copy mode - copy segments without re-encoding when possible
SMART_COPY_MODE = True

# Maximum workers for parallel processing
# For GPU processing, limit to 1-2 to avoid VRAM conflicts
MAX_WORKERS = 1  # Single worker for GPU to maximize utilization

# Timeout settings
MAX_SEGMENT_TIMEOUT = 600  # 10 minutes per segment
MAX_CONCAT_TIMEOUT = 600  # 10 minutes for concatenation

# ═══════════════════════════════════════════════════════════════
# VIDEO SETTINGS
# ═══════════════════════════════════════════════════════════════

# Output resolution settings
MAX_OUTPUT_WIDTH = 1920
MAX_OUTPUT_HEIGHT = 1080

RESOLUTION_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "360p": (640, 360),
}

# Fallback CPU encoding (when GPU unavailable)
ENCODING_PRESET = "medium"  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
CRF_QUALITY = 23  # 18-28, lower is better quality

# Audio settings
AUDIO_BITRATE = "128k"

# Debug overlay (shows segment numbers)
DEBUG_OVERLAY = False

# ═══════════════════════════════════════════════════════════════
# WATERMARK SETTINGS
# ═══════════════════════════════════════════════════════════════

WATERMARK_URL = os.environ.get("WATERMARK_URL", "")
WATERMARK_PADDING = 2
WATERMARK_SCALE = 0.12  # 15% of video width
WATERMARK_OPACITY = 0.8
WATERMARK_POSITION = "bottom_right"  # top_left, top_right, bottom_left, bottom_right

# ═══════════════════════════════════════════════════════════════
# MEMORY OPTIMIZATION
# ═══════════════════════════════════════════════════════════════

# For RTX 5090 with 32GB VRAM, we can be aggressive
GPU_MEMORY_FRACTION = 0.95  # Use 95% of available VRAM
EXTRA_HW_FRAMES = 8  # Buffer frames in GPU memory

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE MONITORING
# ═══════════════════════════════════════════════════════════════

ENABLE_GPU_MONITORING = True  # Monitor GPU usage during processing
PRINT_FFMPEG_OUTPUT = False  # Print FFmpeg output for debugging

# ═══════════════════════════════════════════════════════════════
# CUDA OPTIMIZATION
# ═══════════════════════════════════════════════════════════════

# Environment variables (set automatically by utils/gpu.py)
# These are documented here for reference:
# CUDA_VISIBLE_DEVICES=0
# NVIDIA_VISIBLE_DEVICES=all
# NVIDIA_DRIVER_CAPABILITIES=compute,utility,video
# CUDA_TF32_ENABLED=1
# CUDA_DEVICE_ORDER=PCI_BUS_ID

# ═══════════════════════════════════════════════════════════════
# QUALITY PRESETS
# ═══════════════════════════════════════════════════════════════

ENABLE_COLOR_GRADING = False

# You can define quality presets for different use cases
QUALITY_PRESETS = {
    "ultra": {
        "cq": 18,
        "preset": "p7",
        "rc_lookahead": 32,
        "maxrate": "30M",
        "bufsize": "60M"
    },
    "high": {
        "cq": 20,
        "preset": "p6",
        "rc_lookahead": 20,
        "maxrate": "20M",
        "bufsize": "40M"
    },
    "balanced": {
        "cq": 23,
        "preset": "p5",
        "rc_lookahead": 10,
        "maxrate": "15M",
        "bufsize": "30M"
    },
    "fast": {
        "cq": 25,
        "preset": "p4",
        "rc_lookahead": 0,
        "maxrate": "10M",
        "bufsize": "20M"
    }
}

# Active preset
ACTIVE_PRESET = "high"  # Change this to switch presets

def get_active_preset():
    """Get the active quality preset settings."""
    return QUALITY_PRESETS.get(ACTIVE_PRESET, QUALITY_PRESETS["balanced"])