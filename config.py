import os

# =============================================================================
# PERFORMANCE PRESETS
# =============================================================================

ENABLE_GPU = True
GPU_ENCODER = "h264_nvenc"
PERFORMANCE_PRESET = "quality"

PRESETS = {
    "fast": {
        "cq": 28,             
        "crf": 26,
        "workers": 4,
        "two_pass": False,
        "gpu_preset": "p1",
        "tune": "fastdecode",
        "audio_bitrate": "96k",
        "color_grading": False,
        "encoding": "ultrafast",
    },
    "balanced": {
        "cq": 24,
        "crf": 23,
        "workers": 3,
        "tune": "film",
        "two_pass": False,
        "gpu_preset": "p4",
        "color_grading": True,
        "encoding": "veryfast",
        "audio_bitrate": "128k",
    },
    "quality": {
        "cq": 19,
        "crf": 20,
        "workers": 2,
        "tune": "film",
        "two_pass": True,
        "gpu_preset": "p7",
        "encoding": "medium",
        "color_grading": True,
        "audio_bitrate": "192k",
    }
}

# =============================================================================
# CONFIGURATION
# =============================================================================

EDITMAP_JSON = "edit_map.json"
INPUT_VIDEO = "input_minecraft.mp4"
OUTPUT_VIDEO = "output_spliceo_v2.mp4"

# Load preset settings
PRESET = PRESETS[PERFORMANCE_PRESET]

CQ_QUALITY = PRESET["cq"]
OUTPUT_RESOLUTION = "1080p"
CRF_QUALITY = PRESET["crf"]
TUNE_PARAM = PRESET["tune"]
MAX_WORKERS = PRESET["workers"]
GPU_PRESET = PRESET["gpu_preset"]
ENCODING_PRESET = PRESET["encoding"]
TWO_PASS_ENCODING = PRESET["two_pass"]
AUDIO_BITRATE = PRESET["audio_bitrate"]
ENABLE_COLOR_GRADING = PRESET["color_grading"]

# Advanced settings
DEBUG_OVERLAY = False
SMART_COPY_MODE = True
INCLUDE_FULL_VIDEO = True
MAX_SEGMENT_TIMEOUT = 3600
CACHE_DIR = ".spliceo_cache"

# FFmpeg optimization
FFMPEG_THREADS = 0
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

RESOLUTION_PRESETS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
    "original": None
}

# =============================================================================
# WATERMARK CONFIGURATION
# =============================================================================

WATERMARK_PADDING = 20  # Pixels from edge
WATERMARK_SCALE = 0.08  # 8% of video width
WATERMARK_OPACITY = 0.85
WATERMARK_POSITION = "bottom_left"  # Options: bottom_left, bottom_right, top_left, top_right
WATERMARK_URL = os.getenv("WATERMARK_URL", "")

