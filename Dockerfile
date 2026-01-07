FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04 

# Set environment variables for GPU acceleration
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all
ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,video
ENV LD_LIBRARY_PATH=/opt/ffmpeg/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH}
ENV PATH=/usr/local/cuda/bin:/opt/ffmpeg/bin:${PATH}
ENV FFMPEG_PATH=/opt/ffmpeg/bin/ffmpeg
ENV FFPROBE_PATH=/opt/ffmpeg/bin/ffprobe

# Install build dependencies and tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    yasm \
    nasm \
    cmake \
    git \
    wget \
    pkg-config \
    libx264-dev \
    libx265-dev \
    libmp3lame-dev \
    libopus-dev \
    libvpx-dev \
    libfdk-aac-dev \
    libssl-dev \
    libnuma-dev \
    ca-certificates && \
    apt-get remove -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install NVIDIA Video Codec SDK headers (version 12.2 for CUDA 12.4)
RUN cd /tmp && \
    wget -O nv-codec-headers.tar.gz \
    https://github.com/FFmpeg/nv-codec-headers/releases/download/n12.2.72.0/nv-codec-headers-12.2.72.0.tar.gz && \
    tar -xzf nv-codec-headers.tar.gz && \
    cd nv-codec-headers-12.2.72.0 && \
    make install && \
    cd / && rm -rf /tmp/nv-codec-headers*

# Build FFmpeg with full GPU acceleration (version 6.1.2 - stable)
# Multi-architecture: Ada Lovelace (sm_89), Hopper (sm_90), Blackwell (sm_100, sm_120)
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH}
RUN cd /tmp && \
    git clone --depth 1 --branch n7.1.3 https://git.ffmpeg.org/ffmpeg.git && \
    cd ffmpeg && \
    ./configure \
    --prefix=/opt/ffmpeg \
    --enable-nonfree \
    --enable-gpl \
    --enable-version3 \
    --enable-cuda-nvcc \
    --enable-cuvid \
    --enable-nvenc \
    --enable-nvdec \
    --enable-libnpp \
    --nvccflags="-gencode arch=compute_89,code=sm_89 -gencode arch=compute_90,code=sm_90 -gencode arch=compute_100,code=sm_100 -gencode arch=compute_120,code=sm_120 -O2" \
    --extra-cflags="-I/usr/local/cuda/include" \
    --extra-ldflags="-L/usr/local/cuda/lib64" \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libmp3lame \
    --enable-libopus \
    --enable-libvpx \
    --enable-libfdk-aac \
    --enable-openssl \
    --enable-shared \
    --disable-static \
    --disable-doc \
    --enable-decoder=h264 \
    --enable-decoder=h264_cuvid \
    --enable-decoder=hevc \
    --enable-decoder=hevc_cuvid \
    --enable-decoder=vp9 \
    --enable-decoder=vp9_cuvid \
    --enable-decoder=av1 \
    --enable-decoder=av1_cuvid \
    --enable-encoder=h264_nvenc \
    --enable-encoder=hevc_nvenc \
    --enable-encoder=av1_nvenc \
    --enable-encoder=libx264 \
    --enable-encoder=libx265 \
    --enable-filter=scale_cuda \
    --enable-filter=thumbnail_cuda \
    --enable-filter=overlay_cuda \
    --enable-hwaccel=h264_nvdec \
    --enable-hwaccel=hevc_nvdec \
    --enable-hwaccel=vp9_nvdec \
    --enable-hwaccel=av1_nvdec && \
    make -j$(nproc) && \
    make install && \
    cd / && rm -rf /tmp/ffmpeg

# Add FFmpeg to system path
RUN ln -s /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg && \
    ln -s /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe && \
    ldconfig

# Verify FFmpeg GPU support (non-fatal as build node might not have GPU)
RUN (ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc || echo "Warning: NVENC not found (expected if no GPU during build)") && \
    (ffmpeg -hide_banner -decoders 2>/dev/null | grep cuvid || echo "Warning: CUVID not found (expected if no GPU during build)")

# Install Python dependencies
RUN pip install --no-cache-dir \
    runpod \
    gdown \
    requests \
    numpy \
    pillow


# Copy application files
COPY *.py /
COPY utils/ /utils/
COPY storage/ /storage/
COPY effects/ /effects/
COPY processor/ /processor/

# Set up temp directory with proper permissions
RUN mkdir -p /temp && chmod 777 /temp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD nvidia-smi && ffmpeg -version || exit 1

# Start the worker
CMD ["python", "-u", "/handler.py"]