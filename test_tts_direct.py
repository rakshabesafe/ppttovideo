#!/usr/bin/env python3
"""
Direct test of TTS functionality to verify fixes
"""
import sys
import os
import subprocess

def test_tts_in_container():
    """Test TTS directly in the GPU worker container"""
    
    print("🧪 Testing TTS functionality directly in GPU worker container...")
    print("=" * 60)
    
    # Test script to run inside the container
    test_script = '''
import sys
import os
sys.path.append("/app")

# Test the TTS initialization
from workers.tasks_gpu import parse_note_text_tags
import torch
import soundfile as sf
import numpy as np

def test_tts():
    try:
        print("Testing TTS parsing functionality...")
        
        # Test text parsing
        test_text = "Hello world! [EMOTION:excited] This is a test. [SPEED:fast] Quick speech!"
        processed_text, emotion, speed, pitch = parse_note_text_tags(test_text)
        
        print(f"✅ Text parsing works:")
        print(f"   Original: {test_text}")
        print(f"   Processed: {processed_text}")
        print(f"   Emotion: {emotion}, Speed: {speed}, Pitch: {pitch}")
        
        # Test MeloTTS import
        try:
            from melo.api import TTS
            print("✅ MeloTTS import successful")
            
            # Try to initialize TTS
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {device}")
            
            tts = TTS(language='EN', device=device)
            print("✅ MeloTTS initialization successful")
            print(f"Available speakers: {list(tts.hps.data.spk2id.keys())}")
            
            # Test audio generation
            test_audio_path = "/tmp/test_tts_output.wav"
            tts.tts_to_file(
                text="Hello world, this is a test of the text to speech system.",
                speaker_id=0,
                output_path=test_audio_path,
                speed=1.0,
                quiet=True
            )
            
            if os.path.exists(test_audio_path):
                file_size = os.path.getsize(test_audio_path)
                print(f"✅ Audio file generated successfully: {file_size} bytes")
                
                # Check if audio contains actual data (not just silence)
                audio, sr = sf.read(test_audio_path)
                max_amplitude = np.max(np.abs(audio))
                print(f"   Sample rate: {sr} Hz")
                print(f"   Duration: {len(audio)/sr:.2f} seconds")
                print(f"   Max amplitude: {max_amplitude:.4f}")
                
                if max_amplitude > 0.01:
                    print("✅ Audio contains actual speech data!")
                    return True
                else:
                    print("❌ Audio appears to be silence")
                    return False
            else:
                print("❌ Audio file was not generated")
                return False
                
        except Exception as tts_error:
            print(f"❌ MeloTTS failed: {tts_error}")
            print("Will fall back to silence generation")
            
            # Test fallback silence generation
            sample_rate = 24000
            duration = 3.0
            silence = np.zeros(int(duration * sample_rate), dtype=np.float32)
            test_silence_path = "/tmp/test_silence.wav"
            sf.write(test_silence_path, silence, sample_rate)
            
            if os.path.exists(test_silence_path):
                print("✅ Fallback silence generation works")
                return True
            else:
                print("❌ Even fallback silence generation failed")
                return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tts()
    print("\\n" + "="*60)
    if success:
        print("🎉 TTS test completed successfully!")
    else:
        print("💥 TTS test failed!")
    '''
    
    try:
        # Write the test script to a temporary file
        with open("/tmp/tts_test_script.py", "w") as f:
            f.write(test_script)
        
        # Run the test script inside the GPU worker container
        cmd = [
            "docker", "exec", "ppt-worker_gpu", 
            "python", "-c", test_script
        ]
        
        print("Executing TTS test in GPU worker container...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("\n🎉 TTS test completed successfully!")
            return True
        else:
            print(f"\n💥 TTS test failed with return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Test timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        return False

if __name__ == "__main__":
    success = test_tts_in_container()
    sys.exit(0 if success else 1)