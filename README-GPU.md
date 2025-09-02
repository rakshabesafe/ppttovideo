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

# TTS Timeout Configuration (optional)
TTS_SOFT_TIME_LIMIT=300    # Soft timeout - triggers fallback audio (5 minutes)
TTS_HARD_TIME_LIMIT=360    # Hard timeout - kills hung tasks (6 minutes)

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
| `TTS tasks hang/timeout` | Check timeout settings in `.env`, verify BERT model caching |
| `Audio synthesis fails` | Test TTS components: `docker exec ppt-worker_gpu python test_tts_isolated.py` |

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

The system has multiple fallback layers for robust operation:

### GPU → CPU Fallback
- 🔄 GPU initialization times out (30 seconds)
- 🔄 CUDA/GPU errors occur
- 🔄 Automatically switches to CPU mode

### TTS Synthesis Fallbacks
1. **Voice Cloning (OpenVoice)** → Base TTS (MeloTTS) → Silence Audio
2. **Configurable Timeouts:**
   - Soft timeout (default 5 min): Creates fallback silence audio
   - Hard timeout (default 6 min): Kills hung tasks completely
3. **BERT Model Issues:** Pre-cached models prevent hanging during initialization

This multi-layer approach ensures the pipeline always completes successfully.

## TTS Testing & Debugging

```bash
# Test TTS component isolation
docker exec ppt-worker_gpu python test_tts_isolated.py

# Run comprehensive TTS tests
docker exec ppt-worker_gpu python test_tts_components_runner.py

# Verify BERT model caching
docker exec ppt-worker_gpu python -c "from transformers import BertTokenizer; print('BERT OK')"

# Monitor TTS processing in real-time
docker logs ppt-worker_gpu -f | grep -E "(TTS|synthesis|timeout|fallback)"
```