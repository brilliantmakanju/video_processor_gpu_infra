# Use the correct RunPod PyTorch image tag format
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Install FFmpeg (with NVIDIA hardware accel support)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install RunPod SDK
RUN pip install runpod

# Copy your handler
COPY handler.py /

# Start the worker
CMD ["python", "-u", "/handler.py"]