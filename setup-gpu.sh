#!/bin/bash

# PPT to Video Generator - GPU Setup Script
# This script automatically detects GPU availability and configures the environment

set -e

echo "🔍 Detecting GPU configuration..."

# Check if nvidia-smi is available
if command -v nvidia-smi &> /dev/null; then
    echo "✅ NVIDIA drivers detected"
    
    # Get GPU count
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo "📊 Found $GPU_COUNT GPU(s)"
    
    # Check if nvidia-docker runtime is available
    if docker info 2>/dev/null | grep -q "nvidia"; then
        echo "✅ NVIDIA Docker runtime detected"
        GPU_RUNTIME="nvidia"
        
        # Test GPU access in container
        echo "🧪 Testing GPU access..."
        if docker run --rm --runtime=nvidia nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi &>/dev/null; then
            echo "✅ GPU access test successful"
        else
            echo "⚠️  GPU access test failed, falling back to CPU mode"
            GPU_RUNTIME="runc"
            GPU_COUNT=0
        fi
    else
        echo "⚠️  NVIDIA Docker runtime not found, falling back to CPU mode"
        GPU_RUNTIME="runc"
        GPU_COUNT=0
    fi
else
    echo "⚠️  NVIDIA drivers not found, using CPU-only mode"
    GPU_RUNTIME="runc"
    GPU_COUNT=0
fi

# Create/update .env file
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

echo "📝 Configuring environment file..."

# Copy from example if .env doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "✅ Created $ENV_FILE from $ENV_EXAMPLE"
    else
        echo "❌ No $ENV_EXAMPLE found"
        exit 1
    fi
fi

# Update GPU configuration in .env file
if [ "$GPU_RUNTIME" = "nvidia" ]; then
    echo "🔧 Configuring GPU mode..."
    
    # Update or add GPU settings
    sed -i "s/^GPU_RUNTIME=.*/GPU_RUNTIME=nvidia/" "$ENV_FILE" || echo "GPU_RUNTIME=nvidia" >> "$ENV_FILE"
    sed -i "s/^GPU_COUNT=.*/GPU_COUNT=$GPU_COUNT/" "$ENV_FILE" || echo "GPU_COUNT=$GPU_COUNT" >> "$ENV_FILE"
    
    # Add NVIDIA environment variables if they don't exist
    if ! grep -q "NVIDIA_VISIBLE_DEVICES" "$ENV_FILE"; then
        echo "NVIDIA_VISIBLE_DEVICES=all" >> "$ENV_FILE"
    fi
    if ! grep -q "NVIDIA_DRIVER_CAPABILITIES" "$ENV_FILE"; then
        echo "NVIDIA_DRIVER_CAPABILITIES=compute,utility" >> "$ENV_FILE"
    fi
    
    echo "✅ GPU mode enabled with $GPU_COUNT GPU(s)"
    echo "🚀 TTS audio synthesis will use GPU acceleration"
else
    echo "🔧 Configuring CPU mode..."
    
    # Set CPU mode
    sed -i "s/^GPU_RUNTIME=.*/GPU_RUNTIME=runc/" "$ENV_FILE" || echo "GPU_RUNTIME=runc" >> "$ENV_FILE"
    sed -i "s/^GPU_COUNT=.*/GPU_COUNT=0/" "$ENV_FILE" || echo "GPU_COUNT=0" >> "$ENV_FILE"
    
    echo "✅ CPU mode enabled"
    echo "⏱️  TTS audio synthesis will use CPU with timeout protection"
fi

echo ""
echo "🎯 Configuration Summary:"
echo "   Runtime: $GPU_RUNTIME"
echo "   GPU Count: $GPU_COUNT"
echo "   Config file: $ENV_FILE"
echo ""

if [ "$GPU_RUNTIME" = "nvidia" ]; then
    echo "🚀 Ready to run with GPU acceleration!"
    echo "   Run: docker-compose up --build"
else
    echo "🐢 Ready to run in CPU mode!"
    echo "   Run: docker-compose up --build"
    echo "   Note: Audio synthesis will use fallback with timeout protection"
fi

echo ""
echo "💡 To manually change GPU settings, edit the $ENV_FILE file"