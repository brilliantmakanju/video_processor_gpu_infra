# Use RunPod's PyTorch base with CUDA 12.4.1
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

# Install nv-codec-headers
RUN git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git && \
    cd nv-codec-headers && make install && cd .. && rm -rf nv-codec-headers

# Compile FFmpeg with NVIDIA support
RUN git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg/ && \
    cd ffmpeg && \
    ./configure \
    --enable-nonfree \
    --enable-cuda-nvcc \
    --enable-libnpp \
    --extra-cflags=-I/usr/local/cuda/include \
    --extra-ldflags=-L/usr/local/cuda/lib64 \
    --disable-static \
    --enable-shared \
    --enable-nvenc \
    --enable-nvdec \
    --enable-cuvid \
    --enable-hwaccel=cuda \
    --enable-filter=scale_cuda \
    --enable-libx264 \
    --enable-gpl && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    cd .. && rm -rf ffmpeg

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