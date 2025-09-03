#!/usr/bin/env python3
"""
Test runner for TTS components

This script tests the modular TTS components in a Docker environment
"""

import sys
import os
import tempfile
import time

# Add project paths
sys.path.append('/app')
sys.path.append('/OpenVoice') 
sys.path.append('/src/melotts')

from app.services.tts_service import TextProcessor, MeloTTSEngine, OpenVoiceCloner, TTSProcessor


def test_text_processor():
    """Test text processing functionality"""
    print("\n=== Testing TextProcessor ===")
    
    processor = TextProcessor()
    
    # Test basic parsing
    text = "[EMOTION:excited] [SPEED:fast] Hello world!"
    clean_text, emotion, speed, pitch = processor.parse_note_text_tags(text)
    
    print(f"Input: {text}")
    print(f"Clean text: {clean_text}")
    print(f"Emotion: {emotion}")
    print(f"Speed: {speed}")
    print(f"Pitch: {pitch}")
    
    assert clean_text == "Hello world!"
    assert emotion == "excited"
    assert speed == 1.3
    print("✅ TextProcessor test passed")


def test_melo_tts_engine():
    """Test MeloTTS engine functionality"""
    print("\n=== Testing MeloTTSEngine ===")
    
    engine = MeloTTSEngine(device="cpu")  # Use CPU for testing
    
    try:
        # Test initialization
        print("Initializing MeloTTS...")
        start_time = time.time()
        engine.initialize()
        init_time = time.time() - start_time
        print(f"Initialization took {init_time:.1f}s")
        
        assert engine.is_initialized()
        print(f"Available speakers: {list(engine.speaker_ids.keys())}")
        
        # Test synthesis
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            output_path = tmp.name
        
        try:
            print("Testing text synthesis...")
            result = engine.synthesize_to_file("Hello, this is a test.", output_path)
            
            assert os.path.exists(output_path)
            file_size = os.path.getsize(output_path)
            print(f"Generated audio file: {file_size} bytes")
            assert file_size > 0
            
            print("✅ MeloTTSEngine test passed")
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
                
    except Exception as e:
        print(f"❌ MeloTTSEngine test failed: {e}")
        return False
        
    return True


def test_openvoice_cloner():
    """Test OpenVoice cloner functionality"""
    print("\n=== Testing OpenVoiceCloner ===")
    
    cloner = OpenVoiceCloner(device="cpu")
    
    try:
        # Test initialization
        print("Initializing OpenVoice...")
        start_time = time.time()
        cloner.initialize()
        init_time = time.time() - start_time
        print(f"Initialization took {init_time:.1f}s")
        
        assert cloner.is_initialized()
        
        # Test built-in voice loading
        print("Testing built-in voice loading...")
        embedding = cloner.load_builtin_voice("en-us")
        print(f"Loaded embedding shape: {embedding.shape}")
        assert embedding.numel() > 0
        
        print("✅ OpenVoiceCloner test passed")
        
    except Exception as e:
        print(f"❌ OpenVoiceCloner test failed: {e}")
        return False
        
    return True


def test_tts_processor():
    """Test high-level TTS processor"""
    print("\n=== Testing TTSProcessor ===")
    
    processor = TTSProcessor(device="cpu")
    
    try:
        # Test initialization
        print("Initializing TTS processor...")
        start_time = time.time()
        processor.initialize()
        init_time = time.time() - start_time
        print(f"Initialization took {init_time:.1f}s")
        
        # Test silence creation
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            silence_path = tmp.name
        
        try:
            print("Testing silence creation...")
            result = processor.create_silence(silence_path, duration_seconds=2.0)
            
            assert os.path.exists(silence_path)
            file_size = os.path.getsize(silence_path)
            print(f"Generated silence file: {file_size} bytes")
            assert file_size > 0
            
        finally:
            if os.path.exists(silence_path):
                os.unlink(silence_path)
        
        # Test base synthesis
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            base_path = tmp.name
        
        try:
            print("Testing base synthesis...")
            result = processor.synthesize_base_only("Hello world", base_path)
            
            assert os.path.exists(base_path)
            file_size = os.path.getsize(base_path)
            print(f"Generated base audio: {file_size} bytes")
            assert file_size > 0
            
        finally:
            if os.path.exists(base_path):
                os.unlink(base_path)
        
        print("✅ TTSProcessor test passed")
        
    except Exception as e:
        print(f"❌ TTSProcessor test failed: {e}")
        return False
        
    return True


def main():
    """Run all component tests"""
    print("=== TTS Components Test Runner ===")
    
    tests = [
        ("TextProcessor", test_text_processor),
        ("MeloTTSEngine", test_melo_tts_engine), 
        ("OpenVoiceCloner", test_openvoice_cloner),
        ("TTSProcessor", test_tts_processor)
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            print(f"\n--- Running {name} test ---")
            results[name] = test_func()
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n=== Test Results Summary ===")
    passed = 0
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)