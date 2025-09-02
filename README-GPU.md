# GPU Configuration for PPT to Video Generator

This document explains how to configure GPU support for enhanced TTS audio synthesis performance.

## Quick Setup

Run the automated GPU detection script:

```bash
./setup-gpu.sh
```

This script will:
- ✅ Detect available GPUs
- ✅ Test NVIDIA Docker runtime
- ✅ Configure environment variables
- ✅ Set appropriate runtime mode

## Manual Configuration

If you prefer manual setup or the auto-detection fails:

### 1. Check GPU Availability

```bash
# Check if NVIDIA GPUs are available
nvidia-smi

# Check if NVIDIA Docker runtime is installed
docker info | grep -i nvidia
```

### 2. Configure Environment

Edit `.env` file with appropriate GPU settings:

```bash
# For GPU-enabled systems
GPU_RUNTIME=nvidia
GPU_COUNT=1
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility

# For CPU-only systems  
GPU_RUNTIME=runc
GPU_COUNT=0
```

### 3. Start Services

```bash
docker-compose up --build
```

## System Requirements

### GPU Mode Requirements
- ✅ NVIDIA GPU with CUDA support
- ✅ NVIDIA Docker runtime (`nvidia-docker2`)
- ✅ CUDA drivers installed on host
- ✅ Docker Compose version 3.8+

### CPU Mode (Fallback)
- ✅ Any system with Docker
- ✅ Automatic timeout protection (8-10 minutes)
- ✅ Placeholder audio generation
- ⚠️  Slower TTS processing

## Troubleshooting

### GPU Not Accessible in Container

1. **Check NVIDIA Docker installation:**
   ```bash
   sudo apt-get install nvidia-docker2
   sudo systemctl restart docker
   ```

2. **Test GPU access:**
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
   ```

3. **Verify runtime configuration:**
   ```bash
   docker info | grep -i runtime
   ```

### Common Issues

| Issue | Solution |
|-------|----------|
| `runtime not found` | Install nvidia-docker2 |
| `NVML initialization failed` | Check GPU drivers |
| `No GPUs found` | Verify NVIDIA_VISIBLE_DEVICES |
| `Permission denied` | Run docker with sudo or add user to docker group |

## Performance Comparison

| Mode | Speed | Quality | Requirements |
|------|-------|---------|--------------|
| **GPU Mode** | ⚡ Fast (30-60s per slide) | 🎯 High quality TTS | NVIDIA GPU |
| **CPU Mode** | 🐢 Slow (2-8 mins per slide) | 📢 Placeholder audio | Any system |

## Configuration Examples

### High-Performance Server
```bash
# .env for server with multiple GPUs
GPU_RUNTIME=nvidia
GPU_COUNT=4
NVIDIA_VISIBLE_DEVICES=0,1,2,3
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### Development Laptop
```bash
# .env for laptop with single GPU
GPU_RUNTIME=nvidia  
GPU_COUNT=1
NVIDIA_VISIBLE_DEVICES=0
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### CPU-Only Cloud Instance
```bash
# .env for CPU-only deployment
GPU_RUNTIME=runc
GPU_COUNT=0
# NVIDIA variables not needed
```

## Docker Compose Override

For complex GPU configurations, create `docker-compose.override.yml`:

```yaml
version: '3.8'
services:
  worker_gpu:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '1']  # Specific GPUs
              capabilities: [gpu]
```

## Monitoring GPU Usage

```bash
# Monitor GPU usage during processing
watch nvidia-smi

# Check container GPU access
docker exec ppt-worker_gpu nvidia-smi

# View GPU worker logs
docker logs ppt-worker_gpu -f
```

## Fallback Behavior

The system automatically falls back to CPU mode if:
- 🔄 GPU initialization times out (30 seconds)
- 🔄 TTS synthesis hangs (8 minutes soft timeout)
- 🔄 CUDA/GPU errors occur

This ensures the pipeline always completes, even without GPU support.