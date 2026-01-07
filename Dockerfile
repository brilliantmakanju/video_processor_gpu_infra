FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Set environment variables
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,video

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg wget curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*




























# Install Python dependencies
RUN pip install --no-cache-dir runpod gdown requests

# Copy all modules and directories
COPY *.py /
COPY utils/ /utils/
COPY storage/ /storage/
COPY effects/ /effects/
COPY processor/ /processor/



# Start the worker
CMD ["python", "-u", "/handler.py"]