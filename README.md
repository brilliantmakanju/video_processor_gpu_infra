# Playthrough Processor (Spliceo v2)

A high-performance, serverless-ready video processing engine built with Python and FFmpeg. Designed to run on RunPod, it transforms raw gameplay footage into polished clips based on a dynamic "edit map" JSON configuration.

## 🚀 Features

- **Serverless Ready**: Native support for RunPod serverless workers.
- **GPU Accelerated**: Leverages NVIDIA NVENC for lightning-fast encoding.
- **Dynamic Resolution**: Supports 720p, 1080p, 1440p, and 4K output.
- **Plugin-Based Effects**:
  - **Zoom & Pan**: Dynamic cropping and anchoring.
  - **Speed Control**: Smooth time-scaling (slow-mo/fast-forward).
  - **Captions**: Customizable text overlays with styling.
  - **Color Grading**: Professional LUT-based or manual color adjustments.
  - **Watermarking**: Automated watermarking for free-tier users.
- **Smart Timeline**: Intelligently segments video to minimize re-encoding and maximize quality.
- **Multi-Storage Support**: Integrated with Cloudflare R2, Google Drive, and GoFile.

## 🛠 Architecture

The project is modularized for scalability and maintainability:

- `handler.py`: The entry point for RunPod jobs.
- `processor/`: Core engine logic (Timeline creation, Segment rendering, Final assembly).
- `effects/`: Individual effect implementations using FFmpeg filters.
- `storage/`: Handlers for various cloud storage providers.
- `utils/`: Shared utilities for FFmpeg, GPU detection, and logging.
- `models.py`: Strongly typed data structures for Edits, Subtitles, and Segments.

## 📦 Installation

### Prerequisites
- Python 3.10+
- FFmpeg (with `h264_nvenc` support for GPU acceleration)
- NVIDIA Drivers & CUDA (if using GPU)

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd playthroughprocessor
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables (optional):
   ```bash
   export WATERMARK_URL="https://your-site.com/watermark.png"
   ```

## 🖥 Usage

### RunPod Input Format
The processor expects a JSON input in the following format:

```json
{
  "input": {
    "video_url": "https://storage.com/raw_video.mp4",
    "edits_json_url": "https://storage.com/edit_map.json",
    "output_resolution": "1080p",
    "is_paid_user": false,
    "upload_url": "https://r2-presigned-url.com/...",
    "public_url": "https://cdn.com/final_video.mp4"
  }
}
```

### Edit Map Schema
The `edit_map.json` defines the transformations applied to the video:

```json
{
  "edits": [
    {
      "type": "zoom",
      "start": 0.0,
      "end": 5.5,
      "zoom": 1.2,
      "anchorX": 0.5,
      "anchorY": 0.5,
      "speed": 1.0
    }
  ],
  "subtitles": [
    {
      "text": "Epic Headshot!",
      "start": 2.0,
      "end": 4.0,
      "style": {
        "fontSize": 48,
        "color": "yellow",
        "position": "bottom"
      }
    }
  ]
}
```

## ⚙️ Configuration

Settings can be tuned in `config.py`:

- `ENABLE_GPU`: Toggle NVENC acceleration.
- `PERFORMANCE_PRESET`: Choose between `fast`, `balanced`, or `quality`.
- `WATERMARK_POSITION`: Adjust where the watermark appears for free users.

## 🐳 Docker

Build and run using the provided Dockerfile:

```bash
docker build -t playthrough-processor .
docker run --gpus all playthrough-processor
```

## 📄 License
Proprietary - All Rights Reserved.
