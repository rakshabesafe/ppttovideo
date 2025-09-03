#!/usr/bin/env python3
"""
Test script to verify TTS bypass functionality works correctly
"""

import sys
import os
import time

# Add the app directory to Python path
sys.path.insert(0, '/MWC/code/ppttovideo/app')

from workers.tasks_gpu import synthesize_audio

def test_tts_bypass():
    """Test that the TTS synthesis bypasses hanging and completes quickly"""
    
    print("🧪 Testing TTS bypass functionality...")
    print("=" * 50)
    
    # Test parameters
    job_id = 999  # Test job ID
    slide_number = 1
    note_text = "This is a test slide with some sample text for TTS processing."
    use_builtin_speaker = True
    ref_audio_path = None
    
    start_time = time.time()
    
    try:
        print(f"⏱️  Starting TTS synthesis test at {time.strftime('%H:%M:%S')}")
        print(f"📝 Text: {note_text}")
        print(f"🎯 Expected: Should complete quickly with placeholder audio")
        
        # This should complete quickly now with the bypass
        result = synthesize_audio(job_id, slide_number, note_text, use_builtin_speaker, ref_audio_path)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Test completed successfully!")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📊 Result: {result}")
        
        if duration < 60:  # Should complete in under 1 minute with bypass
            print("🎉 SUCCESS: TTS bypass is working correctly!")
            return True
        else:
            print("❌ FAILED: TTS still taking too long")
            return False
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"❌ Test failed with exception after {duration:.2f} seconds:")
        print(f"💥 Error: {e}")
        return False

if __name__ == "__main__":
    success = test_tts_bypass()
    sys.exit(0 if success else 1)