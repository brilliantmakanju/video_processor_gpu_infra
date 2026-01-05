# Use RunPod's PyTorch base with CUDA 12.4.1 (optimized for RTX 5090)
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Set environment variables for optimal GPU performance
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,video
ENV CUDA_VISIBLE_DEVICES=0

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg has NVIDIA hardware acceleration support
RUN ffmpeg -encoders 2>&1 | grep -i nvenc || echo "Warning: NVENC not detected"

# Install Python dependencies
RUN pip install --no-cache-dir \
    runpod \
    gdown

# Set working directory
WORKDIR /workspace

# Copy handler script
COPY handler.py /workspace/handler.py

# Make handler executable
RUN chmod +x /workspace/handler.py

# Health check to verify GPU availability
RUN nvidia-smi || echo "Warning: nvidia-smi not available"

# Expose port for RunPod (optional)
EXPOSE 8000

# Start the serverless worker
CMD ["python", "-u", "/workspace/handler.py"]