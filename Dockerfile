# Official lightweight RunPod base with CUDA + Python
FROM runpod/base:latest

# Set working directory
WORKDIR /workspace

# Install FFmpeg with NVIDIA support
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install RunPod SDK
RUN pip install runpod

# Copy all your files (handler, test video, edit.json, etc.)
COPY . /workspace

# Start the serverless worker
CMD ["python", "-u", "/workspace/handler.py"]