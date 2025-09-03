#!/usr/bin/env python3
"""
Isolated unit test for TTS voice generation to identify the root cause of hanging issues.
This test isolates the TTS functionality from the full Celery task pipeline.
"""

import os
import sys
import time
import torch
import soundfile as sf
from minio import Minio
import tempfile
import signal

# Add project paths
sys.path.append('/app')
sys.path.append('/OpenVoice')
sys.path.append('/src/melotts')

print("=== TTS Voice Generation Unit Test ===")
print(f"Python version: {sys.version}")
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Test timed out")

def test_melo_tts_initialization():
    """Test MeloTTS initialization in isolation"""
    print("\n--- Testing MeloTTS Initialization ---")
    
    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(60)  # 60 second timeout
    
    try:
        start_time = time.time()
        
        # Initialize MeloTTS
        print("Importing MeloTTS...")
        from melo.api import TTS
        print(f"MeloTTS import successful ({time.time() - start_time:.1f}s)")
        
        print("Initializing TTS model...")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        base_tts = TTS(language='EN', device=device)
        print(f"TTS initialization successful ({time.time() - start_time:.1f}s)")
        
        base_speaker_ids = base_tts.hps.data.spk2id
        print(f"Available speakers: {list(base_speaker_ids.keys())}")
        
        signal.alarm(0)  # Cancel timeout
        return base_tts, time.time() - start_time
        
    except TimeoutException:
        print("ERROR: MeloTTS initialization timed out after 60 seconds")
        return None, None
    except Exception as e:
        signal.alarm(0)
        print(f"ERROR: MeloTTS initialization failed: {e}")
        return None, None

def test_basic_tts_synthesis(base_tts):
    """Test basic TTS synthesis without voice cloning"""
    print("\n--- Testing Basic TTS Synthesis ---")
    
    if base_tts is None:
        print("Skipping synthesis test - TTS not initialized")
        return False
        
    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30 second timeout
    
    try:
        start_time = time.time()
        
        test_text = "Hello, this is a test of the TTS system."
        output_path = "/tmp/test_tts_output.wav"
        
        print(f"Synthesizing: '{test_text}'")
        
        base_tts.tts_to_file(
            text=test_text,
            speaker_id=0,  # Default English speaker
            output_path=output_path,
            speed=1.0,
            quiet=True
        )
        
        # Check if file was created
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"SUCCESS: Audio file created ({file_size} bytes) in {time.time() - start_time:.1f}s")
            
            # Clean up
            os.remove(output_path)
            
            signal.alarm(0)
            return True
        else:
            print("ERROR: Audio file was not created")
            signal.alarm(0)
            return False
            
    except TimeoutException:
        print("ERROR: TTS synthesis timed out after 30 seconds")
        return False
    except Exception as e:
        signal.alarm(0)
        print(f"ERROR: TTS synthesis failed: {e}")
        return False

def test_openvoice_initialization():
    """Test OpenVoice initialization"""
    print("\n--- Testing OpenVoice Initialization ---")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30 second timeout
    
    try:
        start_time = time.time()
        
        print("Importing OpenVoice components...")
        from openvoice import se_extractor
        from openvoice.api import ToneColorConverter
        print(f"OpenVoice imports successful ({time.time() - start_time:.1f}s)")
        
        print("Initializing ToneColorConverter...")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        tone_color_converter = ToneColorConverter('checkpoints_v2/checkpoints_v2/converter/config.json', device=device)
        print(f"ToneColorConverter initialization successful ({time.time() - start_time:.1f}s)")
        
        signal.alarm(0)
        return True
        
    except TimeoutException:
        print("ERROR: OpenVoice initialization timed out after 30 seconds")
        return False
    except Exception as e:
        signal.alarm(0)
        print(f"ERROR: OpenVoice initialization failed: {e}")
        return False

def test_gpu_memory():
    """Test GPU memory usage"""
    print("\n--- Testing GPU Memory ---")
    
    if not torch.cuda.is_available():
        print("CUDA not available, skipping GPU memory test")
        return
        
    try:
        print(f"GPU Memory before: {torch.cuda.memory_allocated()/1024**3:.2f} GB allocated, {torch.cuda.memory_reserved()/1024**3:.2f} GB reserved")
        
        # Create a test tensor to check GPU functionality
        test_tensor = torch.randn(1000, 1000).cuda()
        result = torch.mm(test_tensor, test_tensor)
        
        print(f"GPU Memory after test: {torch.cuda.memory_allocated()/1024**3:.2f} GB allocated, {torch.cuda.memory_reserved()/1024**3:.2f} GB reserved")
        print("GPU functionality test: PASSED")
        
        del test_tensor, result
        torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"GPU test failed: {e}")

def main():
    """Run all TTS unit tests"""
    print("Starting TTS isolation tests...")
    
    # Test GPU memory first
    test_gpu_memory()
    
    # Test OpenVoice initialization
    openvoice_ok = test_openvoice_initialization()
    
    # Test MeloTTS initialization
    base_tts, init_time = test_melo_tts_initialization()
    
    if base_tts is not None:
        print(f"\n✅ MeloTTS initialized successfully in {init_time:.1f}s")
        
        # Test basic synthesis
        synthesis_ok = test_basic_tts_synthesis(base_tts)
        
        if synthesis_ok:
            print("\n✅ Basic TTS synthesis working")
        else:
            print("\n❌ Basic TTS synthesis failed")
    else:
        print("\n❌ MeloTTS initialization failed")
        
    print("\n=== Test Summary ===")
    print(f"OpenVoice initialization: {'✅ PASS' if openvoice_ok else '❌ FAIL'}")
    print(f"MeloTTS initialization: {'✅ PASS' if base_tts is not None else '❌ FAIL'}")
    if base_tts is not None:
        print(f"TTS synthesis: {'✅ PASS' if synthesis_ok else '❌ FAIL'}")
    
    return base_tts is not None and (base_tts is None or synthesis_ok)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)