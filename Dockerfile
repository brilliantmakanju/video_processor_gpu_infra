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


# Install Python dependencies
RUN pip install --no-cache-dir \
    runpod \
    gdown
   
# Copy your handler
COPY handler.py /

# Start the worker
CMD ["python", "-u", "/handler.py"]