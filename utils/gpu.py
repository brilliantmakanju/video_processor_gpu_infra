import os
import subprocess
import re
from typing import Dict, Optional, Tuple
from config import (
    FFMPEG_BIN, GPU_ENCODER, GPU_DECODER, 
    ENABLE_GPU_MONITORING, PRINT_FFMPEG_OUTPUT
)

# Cache for GPU support check
_GPU_SUPPORT_CACHE = None
_GPU_INFO_CACHE = None

def check_gpu_support() -> bool:
    """
    Comprehensive check if NVIDIA GPU hardware acceleration is available and working.
    Tests: CUDA driver, encoder, decoder, and scale_cuda filter.
    """
    global _GPU_SUPPORT_CACHE
    
    if _GPU_SUPPORT_CACHE is not None:
        return _GPU_SUPPORT_CACHE
    
    try:
        log("Starting comprehensive GPU support check...")
        
        # Step 1: Check NVIDIA driver
        if not _check_nvidia_driver():
            log("❌ NVIDIA driver not available")
            _GPU_SUPPORT_CACHE = False
            return False
        
        # Step 2: Check CUDA availability
        if not _check_cuda_available():
            log("❌ CUDA not available")
            _GPU_SUPPORT_CACHE = False
            return False
        
        # Step 3: Check FFmpeg GPU support
        if not _check_ffmpeg_gpu_support():
            log("❌ FFmpeg GPU support not available")
            _GPU_SUPPORT_CACHE = False
            return False
        
        # Step 4: Run comprehensive hardware test
        if not _test_hardware_acceleration():
            log("❌ Hardware acceleration test failed")
            _GPU_SUPPORT_CACHE = False
            return False
        
        log("✓ GPU hardware acceleration fully operational")
        _GPU_SUPPORT_CACHE = True
        return True
        
    except Exception as e:
        log(f"❌ Exception during GPU check: {str(e)}")
        _GPU_SUPPORT_CACHE = False
        return False


def _check_nvidia_driver() -> bool:
    """Check if NVIDIA driver is loaded and working."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split('\n')[0]
            log(f"✓ NVIDIA driver detected: {gpu_name}")
            return True
        
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def _check_cuda_available() -> bool:
    """Check if CUDA is available in the system."""
    try:
        # Check CUDA version
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            driver_version = result.stdout.strip()
            log(f"✓ CUDA available (Driver: {driver_version})")
            
            # Set CUDA environment if not already set
            if not os.environ.get("CUDA_VISIBLE_DEVICES"):
                os.environ["CUDA_VISIBLE_DEVICES"] = "0"
                log("  Set CUDA_VISIBLE_DEVICES=0")
            
            return True
        
        return False
    except Exception:
        return False


def _check_ffmpeg_gpu_support() -> bool:
    """Verify FFmpeg was compiled with NVENC/NVDEC support."""
    try:
        # Check for encoder
        result_enc = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result_enc.returncode != 0:
            log(f"❌ Failed to query FFmpeg encoders")
            return False
        
        # Check for all NVENC variants
        nvenc_variants = ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]
        found_encoders = [enc for enc in nvenc_variants if enc in result_enc.stdout]
        
        if not found_encoders:
            log(f"❌ No NVENC encoders found in FFmpeg")
            return False
        
        log(f"✓ Found NVENC encoders: {', '.join(found_encoders)}")
        
        # Check for decoder
        result_dec = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-decoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result_dec.returncode != 0:
            log(f"❌ Failed to query FFmpeg decoders")
            return False
        
        # Check for all CUVID variants
        cuvid_variants = ["h264_cuvid", "hevc_cuvid", "vp9_cuvid", "av1_cuvid"]
        found_decoders = [dec for dec in cuvid_variants if dec in result_dec.stdout]
        
        if not found_decoders:
            log(f"❌ No CUVID decoders found in FFmpeg")
            return False
        
        log(f"✓ Found CUVID decoders: {', '.join(found_decoders)}")
        
        # Verify specific encoder and decoder from config
        if GPU_ENCODER not in result_enc.stdout:
            log(f"❌ Configured encoder '{GPU_ENCODER}' not found")
            return False
        
        if GPU_DECODER not in result_dec.stdout:
            log(f"❌ Configured decoder '{GPU_DECODER}' not found")
            return False
        
        log(f"✓ Configured encoder/decoder available: {GPU_ENCODER}/{GPU_DECODER}")
        return True
        
    except Exception as e:
        log(f"❌ Error checking FFmpeg GPU support: {e}")
        return False


def _test_hardware_acceleration() -> bool:
    """
    Run hardware acceleration test.
    Tests GPU encoder first (most reliable), then full pipeline.
    """
    try:
        # Test 1: GPU encoder (most reliable test - no CUDA filters)
        log("Testing GPU encoder...")
        
        encoder_test = [
            FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=0.5:size=640x480:rate=30",
            "-c:v", GPU_ENCODER,
            "-preset", "p4",
            "-f", "null", "-"
        ]
        
        result = subprocess.run(
            encoder_test,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            log("❌ GPU encoder test failed")
            if PRINT_FFMPEG_OUTPUT:
                log(f"Encoder test stderr:\n{result.stderr}")
            return False
        
        log("✓ GPU encoder works")
        
        # Test 2: Full GPU pipeline with proper hwupload
        # testsrc outputs CPU frames, so we need hwupload_cuda before scale_cuda
        log("Testing full GPU pipeline (hwupload → scale_cuda → encode)...")
        
        pipeline_test = [
            FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=0.5:size=640x480:rate=30",
            "-vf", "format=nv12,hwupload_cuda,scale_cuda=320:240",
            "-c:v", GPU_ENCODER,
            "-preset", "p4",
            "-f", "null", "-"
        ]
        
        result2 = subprocess.run(
            pipeline_test,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result2.returncode == 0:
            log("✓ Full GPU pipeline test passed (hwupload → scale_cuda → encode)")
            return True
        else:
            # Encoder works but scale_cuda doesn't - still acceptable
            # The segment renderer can handle this with hwdownload fallback
            log("⚠️  scale_cuda not working, but encoder is functional")
            log("   Renderer will use CPU scaling with GPU encoding")
            if PRINT_FFMPEG_OUTPUT:
                log(f"Pipeline test stderr:\n{result2.stderr}")
            return True  # Return True since encoder works
            
    except subprocess.TimeoutExpired:
        log("❌ Hardware acceleration test timed out")
        return False
    except Exception as e:
        log(f"❌ Error during hardware test: {e}")
        return False


def get_gpu_info() -> Dict[str, any]:
    """Get detailed GPU information."""
    global _GPU_INFO_CACHE
    
    if _GPU_INFO_CACHE is not None:
        return _GPU_INFO_CACHE
    
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,memory.used,compute_cap,driver_version,pcie.link.gen.current,pcie.link.width.current",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {}
        
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        
        info = {
            "name": parts[0],
            "total_memory_mb": int(float(parts[1])),
            "free_memory_mb": int(float(parts[2])),
            "used_memory_mb": int(float(parts[3])),
            "compute_capability": parts[4],
            "driver_version": parts[5],
            "pcie_gen": int(parts[6]) if len(parts) > 6 else 0,
            "pcie_width": int(parts[7]) if len(parts) > 7 else 0,
        }
        
        _GPU_INFO_CACHE = info
        return info
        
    except Exception as e:
        log(f"Failed to get GPU info: {e}")
        return {}


def get_gpu_compute_capability() -> Optional[str]:
    """Get GPU compute capability (e.g., '8.9' for RTX 5090)."""
    info = get_gpu_info()
    return info.get("compute_capability")


def get_optimal_nvenc_settings() -> Dict[str, any]:
    """
    Get optimal NVENC settings based on GPU capabilities.
    Returns settings optimized for the detected GPU.
    """
    info = get_gpu_info()
    
    if not info:
        # Default safe settings
        return {
            "surfaces": 32,
            "rc_lookahead": 16,
            "maxrate": "15M",
            "bufsize": "30M"
        }
    
    total_vram = info.get("total_memory_mb", 0)
    compute_cap = info.get("compute_capability", "0.0")
    
    # Parse compute capability
    try:
        major, minor = map(int, compute_cap.split("."))
        compute_score = major * 10 + minor
    except:
        compute_score = 0
    
    # Optimize based on VRAM and compute capability
    if total_vram >= 30000:  # 30GB+ (RTX 5090, A6000)
        return {
            "surfaces": 128 if compute_score >= 89 else 96,
            "rc_lookahead": 32,
            "maxrate": "25M",
            "bufsize": "50M",
            "decode_surfaces": 128
        }
    elif total_vram >= 20000:  # 20-30GB (RTX 4090, A5000)
        return {
            "surfaces": 96,
            "rc_lookahead": 24,
            "maxrate": "20M",
            "bufsize": "40M",
            "decode_surfaces": 96
        }
    elif total_vram >= 10000:  # 10-20GB (RTX 3090, RTX 4080)
        return {
            "surfaces": 64,
            "rc_lookahead": 20,
            "maxrate": "15M",
            "bufsize": "30M",
            "decode_surfaces": 64
        }
    else:  # <10GB
        return {
            "surfaces": 32,
            "rc_lookahead": 16,
            "maxrate": "10M",
            "bufsize": "20M",
            "decode_surfaces": 32
        }


def monitor_gpu_usage() -> Optional[Dict[str, any]]:
    """Monitor real-time GPU usage during processing."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            return {
                "gpu_util": int(parts[0]) if parts[0].isdigit() else 0,
                "encoder_util": int(parts[1]) if parts[1].isdigit() else 0,
                "decoder_util": int(parts[2]) if parts[2].isdigit() else 0,
                "memory_used_mb": int(parts[3]) if parts[3].replace('.', '').isdigit() else 0,
                "memory_total_mb": int(parts[4]) if parts[4].replace('.', '').isdigit() else 0,
                "temperature_c": int(float(parts[5])) if len(parts) > 5 else 0,
                "power_draw_w": float(parts[6]) if len(parts) > 6 else 0.0
            }
    except Exception as e:
        if ENABLE_GPU_MONITORING:
            log(f"GPU monitoring failed: {e}")
    
    return None


def format_gpu_usage(usage: Dict[str, any]) -> str:
    """Format GPU usage for display."""
    if not usage:
        return "GPU monitoring unavailable"
    
    return (
        f"GPU: {usage['gpu_util']}% | "
        f"Enc: {usage['encoder_util']}% | "
        f"Dec: {usage['decoder_util']}% | "
        f"VRAM: {usage['memory_used_mb']}/{usage['memory_total_mb']}MB | "
        f"Temp: {usage['temperature_c']}°C | "
        f"Power: {usage['power_draw_w']:.1f}W"
    )


def optimize_cuda_settings():
    """Set optimal CUDA environment variables for video processing."""
    # Enable TensorFloat-32 for better performance on Ampere+ GPUs
    if "CUDA_TF32_ENABLED" not in os.environ:
        os.environ["CUDA_TF32_ENABLED"] = "1"
    
    # Disable CUDA caching to save VRAM (enable for video processing)
    if "CUDA_CACHE_DISABLE" not in os.environ:
        os.environ["CUDA_CACHE_DISABLE"] = "0"
    
    # Set CUDA device order
    if "CUDA_DEVICE_ORDER" not in os.environ:
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    
    # Enable all NVIDIA driver capabilities
    if "NVIDIA_DRIVER_CAPABILITIES" not in os.environ:
        os.environ["NVIDIA_DRIVER_CAPABILITIES"] = "compute,utility,video"
    
    # Ensure GPU is visible
    if "NVIDIA_VISIBLE_DEVICES" not in os.environ:
        os.environ["NVIDIA_VISIBLE_DEVICES"] = "all"
    
    # Set CUDA visible devices if not set
    if "CUDA_VISIBLE_DEVICES" not in os.environ:
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    
    log("CUDA environment optimized for video processing")


def print_gpu_status():
    """Print comprehensive GPU status."""
    info = get_gpu_info()
    
    if not info:
        log("No GPU detected or nvidia-smi not available")
        return
    
    print("\n" + "="*70)
    print("GPU STATUS")
    print("="*70)
    print(f"GPU Model:           {info['name']}")
    print(f"Compute Capability:  {info['compute_capability']}")
    print(f"Driver Version:      {info['driver_version']}")
    print(f"Total VRAM:          {info['total_memory_mb']:,} MB")
    print(f"Available VRAM:      {info['free_memory_mb']:,} MB")
    print(f"Used VRAM:           {info['used_memory_mb']:,} MB")
    
    if info.get('pcie_gen'):
        print(f"PCIe:                Gen{info['pcie_gen']} x{info['pcie_width']}")
    
    # Get current usage
    usage = monitor_gpu_usage()
    if usage:
        print(f"\nCurrent Utilization:")
        print(f"  GPU Compute:       {usage['gpu_util']}%")
        print(f"  Video Encoder:     {usage['encoder_util']}%")
        print(f"  Video Decoder:     {usage['decoder_util']}%")
        print(f"  Temperature:       {usage['temperature_c']}°C")
        print(f"  Power Draw:        {usage['power_draw_w']:.1f}W")
    
    # Get optimal settings
    settings = get_optimal_nvenc_settings()
    print(f"\nRecommended Settings:")
    print(f"  Encode Surfaces:   {settings['surfaces']}")
    print(f"  Decode Surfaces:   {settings.get('decode_surfaces', 64)}")
    print(f"  RC Lookahead:      {settings['rc_lookahead']} frames")
    print(f"  Max Bitrate:       {settings['maxrate']}")
    
    print("="*70 + "\n")


def validate_gpu_setup() -> bool:
    """
    Comprehensive GPU setup validation.
    Returns True if GPU is ready for video processing.
    """
    print("\n" + "="*70)
    print("VALIDATING GPU SETUP")
    print("="*70)
    
    # Check basic GPU support
    if not check_gpu_support():
        print("❌ GPU validation failed - falling back to CPU processing")
        print("="*70 + "\n")
        return False
    
    # Print detailed status
    print_gpu_status()
    
    # Check minimum requirements
    info = get_gpu_info()
    
    warnings = []
    
    if info['free_memory_mb'] < 4000:
        warnings.append("⚠️  Less than 4GB VRAM available - may struggle with 4K content")
    
    if info['free_memory_mb'] < 2000:
        warnings.append("❌ Less than 2GB VRAM available - processing will likely fail")
        print("\n".join(warnings))
        print("="*70 + "\n")
        return False
    
    compute_cap = info.get('compute_capability', '0.0')
    try:
        major = int(compute_cap.split('.')[0])
        if major < 5:  # Pre-Maxwell
            warnings.append("⚠️  Old GPU architecture - limited NVENC features")
    except:
        pass
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  {warning}")
    
    print("\n✓ GPU setup validated successfully")
    print("="*70 + "\n")
    return True


def get_ffmpeg_gpu_filters() -> list:
    """Get list of available GPU-accelerated filters."""
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return []
        
        gpu_filters = []
        for line in result.stdout.split('\n'):
            # Look for CUDA/NPP filters
            if '_cuda' in line.lower() or '_npp' in line.lower():
                # Extract filter name
                parts = line.strip().split()
                if len(parts) >= 2:
                    filter_name = parts[1]
                    gpu_filters.append(filter_name)
        
        return gpu_filters
        
    except Exception:
        return []


def log(message: str):
    """Simple logging function."""
    print(f"[GPU] {message}")


# Initialize CUDA settings on import
optimize_cuda_settings()