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

# Install build dependencies and tools (INCLUDING FREETYPE FOR DRAWTEXT)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    yasm \
    nasm \
    cmake \
    git \
    pkg-config \
    libx264-dev \
    libx265-dev \
    libmp3lame-dev \
    libopus-dev \
    libvpx-dev \
    libfdk-aac-dev \
    libssl-dev \
    libnuma-dev \
    libfreetype6-dev \
    libfontconfig1-dev && \
    apt-get remove -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install NVIDIA Video Codec SDK headers
RUN cd /tmp && \
    wget -O nv-codec-headers.tar.gz \
    https://github.com/FFmpeg/nv-codec-headers/releases/download/n12.2.72.0/nv-codec-headers-12.2.72.0.tar.gz && \
    tar -xzf nv-codec-headers.tar.gz && \
    cd nv-codec-headers-12.2.72.0 && \
    make install && \
    cd / && rm -rf /tmp/nv-codec-headers*

# Set PKG_CONFIG_PATH for FFmpeg configure
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH}

# Build FFmpeg with GPU support + DRAWTEXT filter
# Multi-GPU support: L4 (sm_89), H100 (sm_90), RTX 5090 (sm_100)
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
    --nvccflags="-gencode arch=compute_89,code=sm_89 -gencode arch=compute_90,code=sm_90 -gencode arch=compute_100,code=sm_100 -O2" \
    --disable-ptx \
    --extra-cflags="-I/usr/local/cuda/include" \
    --extra-ldflags="-L/usr/local/cuda/lib64" \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libmp3lame \
    --enable-libopus \
    --enable-libvpx \
    --enable-libfdk-aac \
    --enable-openssl \
    --enable-libfreetype \
    --enable-libfontconfig \
    --enable-filter=drawtext \
    --enable-shared \
    --disable-static \
    --disable-doc && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    cd / && rm -rf /tmp/ffmpeg

# Create symbolic links
RUN ln -sf /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg && \
    ln -sf /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe

# Verify FFmpeg build (non-fatal warnings)
RUN ffmpeg -version && \
    (ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc || echo "Note: NVENC will be available at runtime") && \
    (ffmpeg -hide_banner -filters 2>/dev/null | grep drawtext || echo "Note: drawtext filter will be available at runtime") && \
    (ffmpeg -hide_banner -hwaccels 2>/dev/null | grep cuda || echo "Note: CUDA hwaccel will be available at runtime")

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

# Set up temp directory
RUN mkdir -p /temp && chmod 777 /temp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD nvidia-smi && ffmpeg -version || exit 1

# Start the worker
CMD ["python", "-u", "/handler.py"]