#!/usr/bin/env python3
"""
Unit tests for TTS service components

Tests each TTS component in isolation:
- TextProcessor
- MeloTTSEngine  
- OpenVoiceCloner
- TTSProcessor
"""

import unittest
import tempfile
import os
import sys
import torch
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Add project paths
sys.path.append('/app')
sys.path.append('/OpenVoice')
sys.path.append('/src/melotts')

from app.services.tts_service import (
    TextProcessor, MeloTTSEngine, OpenVoiceCloner, TTSProcessor,
    TTSException, MeloTTSException, OpenVoiceException
)


class TestTextProcessor(unittest.TestCase):
    """Test text processing and tag parsing functionality"""
    
    def setUp(self):
        self.processor = TextProcessor()
    
    def test_parse_basic_text(self):
        """Test parsing text without any tags"""
        text = "Hello, this is a test."
        clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(text)
        
        self.assertEqual(clean_text, "Hello, this is a test.")
        self.assertEqual(emotion, "neutral")
        self.assertEqual(speed, 1.0)
        self.assertEqual(pitch, 1.0)
    
    def test_parse_emotion_tags(self):
        """Test parsing emotion tags"""
        test_cases = [
            ("[EMOTION:excited] Hello!", "Hello!", "excited"),
            ("[EMOTION:sad] Goodbye.", "Goodbye.", "sad"),
            ("[EMOTION:HAPPY] Great news!", "Great news!", "happy"),
            ("Normal text", "Normal text", "neutral")
        ]
        
        for input_text, expected_clean, expected_emotion in test_cases:
            with self.subTest(input_text=input_text):
                clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(input_text)
                self.assertEqual(clean_text, expected_clean)
                self.assertEqual(emotion, expected_emotion)
    
    def test_parse_speed_tags(self):
        """Test parsing speed tags"""
        test_cases = [
            ("[SPEED:fast] Quick speech", "Quick speech", 1.3),
            ("[SPEED:slow] Slow speech", "Slow speech", 0.7),
            ("[SPEED:1.5] Custom speed", "Custom speed", 1.5),
            ("[SPEED:0.5] Very slow", "Very slow", 0.5),
            ("[SPEED:3.0] Too fast", "Too fast", 2.0),  # Should clamp to 2.0
            ("Normal speed", "Normal speed", 1.0)
        ]
        
        for input_text, expected_clean, expected_speed in test_cases:
            with self.subTest(input_text=input_text):
                clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(input_text)
                self.assertEqual(clean_text, expected_clean)
                self.assertAlmostEqual(speed, expected_speed)
    
    def test_parse_pitch_tags(self):
        """Test parsing pitch tags"""
        test_cases = [
            ("[PITCH:high] High voice", "High voice", 1.2),
            ("[PITCH:low] Low voice", "Low voice", 0.8),
            ("[PITCH:1.5] Custom pitch", "Custom pitch", 1.5),
            ("Normal pitch", "Normal pitch", 1.0)
        ]
        
        for input_text, expected_clean, expected_pitch in test_cases:
            with self.subTest(input_text=input_text):
                clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(input_text)
                self.assertEqual(clean_text, expected_clean)
                self.assertAlmostEqual(pitch, expected_pitch)
    
    def test_parse_multiple_tags(self):
        """Test parsing text with multiple tags"""
        text = "[EMOTION:excited] [SPEED:fast] [PITCH:high] Hello world!"
        clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(text)
        
        self.assertEqual(clean_text, "Hello world!")
        self.assertEqual(emotion, "excited")
        self.assertEqual(speed, 1.3)
        self.assertEqual(pitch, 1.2)
    
    def test_parse_special_tags(self):
        """Test parsing pause and emphasis tags"""
        text = "Hello [PAUSE:2] [EMPHASIS:world] test"
        clean_text, emotion, speed, pitch = self.processor.parse_note_text_tags(text)
        
        self.assertEqual(clean_text, "Hello ,, WORLD test")
        self.assertEqual(emotion, "neutral")


class TestMeloTTSEngine(unittest.TestCase):
    """Test MeloTTS engine functionality"""
    
    def setUp(self):
        self.engine = MeloTTSEngine(device="cpu")  # Use CPU for testing
    
    @patch('app.services.tts_service.TTS')
    def test_initialization(self, mock_tts_class):
        """Test MeloTTS engine initialization"""
        mock_tts = Mock()
        mock_tts.hps.data.spk2id = {'EN-US': 0, 'EN-BR': 1}
        mock_tts_class.return_value = mock_tts
        
        self.engine.initialize()
        
        self.assertTrue(self.engine.is_initialized())
        self.assertEqual(self.engine.speaker_ids, {'EN-US': 0, 'EN-BR': 1})
        mock_tts_class.assert_called_once_with(language='EN', device='cpu')
    
    def test_initialization_failure(self):
        """Test MeloTTS initialization failure handling"""
        with patch('app.services.tts_service.TTS', side_effect=Exception("Mock error")):
            with self.assertRaises(MeloTTSException):
                self.engine.initialize()
    
    @patch('app.services.tts_service.torch.zeros')
    @patch('app.services.tts_service.sf.write')
    def test_synthesize_silence(self, mock_sf_write, mock_zeros):
        """Test synthesis of silence tag"""
        mock_zeros.return_value = Mock()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            output_path = tmp.name
        
        try:
            result = self.engine.synthesize_to_file("[SILENCE]", output_path)
            self.assertEqual(result, output_path)
            mock_zeros.assert_called_once_with(24000)  # 1 second at 24kHz
            mock_sf_write.assert_called_once()
        finally:
            os.unlink(output_path)
    
    @patch('app.services.tts_service.TTS')
    def test_synthesize_text(self, mock_tts_class):
        """Test text synthesis"""
        mock_tts = Mock()
        mock_tts_class.return_value = mock_tts
        
        self.engine.tts_model = mock_tts  # Skip initialization
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            output_path = tmp.name
            # Create the file to simulate successful synthesis
            with open(output_path, 'w') as f:
                f.write("dummy audio")
        
        try:
            result = self.engine.synthesize_to_file("Hello world", output_path, speed=1.2)
            self.assertEqual(result, output_path)
            
            mock_tts.tts_to_file.assert_called_once_with(
                text="Hello world",
                speaker_id=0,
                output_path=output_path,
                speed=1.2,
                quiet=True
            )
        finally:
            os.unlink(output_path)


class TestOpenVoiceCloner(unittest.TestCase):
    """Test OpenVoice cloner functionality"""
    
    def setUp(self):
        self.cloner = OpenVoiceCloner(device="cpu")
    
    @patch('app.services.tts_service.ToneColorConverter')
    @patch('app.services.tts_service.torch.load')
    def test_initialization(self, mock_torch_load, mock_converter_class):
        """Test OpenVoice cloner initialization"""
        mock_converter = Mock()
        mock_converter_class.return_value = mock_converter
        mock_torch_load.return_value = torch.tensor([1, 2, 3])
        
        self.cloner.initialize()
        
        self.assertTrue(self.cloner.is_initialized())
        mock_converter_class.assert_called_once()
        mock_torch_load.assert_called_once()
    
    @patch('app.services.tts_service.torch.load')
    def test_load_builtin_voice(self, mock_torch_load):
        """Test loading built-in voice embedding"""
        mock_embedding = torch.tensor([1, 2, 3, 4])
        mock_torch_load.return_value = mock_embedding
        
        result = self.cloner.load_builtin_voice("en-us")
        
        self.assertTrue(torch.equal(result, mock_embedding))
        mock_torch_load.assert_called_once_with(
            'checkpoints_v2/checkpoints_v2/base_speakers/ses/en-us.pth',
            map_location='cpu'
        )
    
    @patch('app.services.tts_service.se_extractor')
    @patch('app.services.tts_service.librosa.load')
    @patch('app.services.tts_service.librosa.effects.trim')
    @patch('app.services.tts_service.sf.write')
    def test_extract_voice_from_audio(self, mock_sf_write, mock_trim, mock_load, mock_se_extractor):
        """Test voice extraction from audio data"""
        # Setup mocks
        mock_load.return_value = (np.array([1, 2, 3, 4]), 24000)
        mock_trim.return_value = (np.array([1, 2, 3]), None)
        mock_se_extractor.get_se.return_value = (torch.tensor([5, 6, 7]), "test")
        
        self.cloner.tone_converter = Mock()  # Mock initialized converter
        
        audio_data = b"fake audio data"
        result = self.cloner.extract_voice_from_audio(audio_data, "wav")
        
        self.assertTrue(torch.equal(result, torch.tensor([5, 6, 7])))
        mock_load.assert_called_once()
        mock_se_extractor.get_se.assert_called_once()
    
    def test_clone_voice(self):
        """Test voice cloning operation"""
        mock_converter = Mock()
        self.cloner.tone_converter = mock_converter
        self.cloner.source_se = torch.tensor([1, 2])
        
        target_embedding = torch.tensor([3, 4])
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_input:
            input_path = tmp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_output:
            output_path = tmp_output.name
            # Create output file to simulate successful conversion
            with open(output_path, 'w') as f:
                f.write("cloned audio")
        
        try:
            result = self.cloner.clone_voice(input_path, target_embedding, output_path)
            self.assertEqual(result, output_path)
            
            mock_converter.convert.assert_called_once_with(
                audio_src_path=input_path,
                src_se=torch.tensor([1, 2]),
                tgt_se=target_embedding,
                output_path=output_path,
                message="Converting voice..."
            )
        finally:
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)


class TestTTSProcessor(unittest.TestCase):
    """Test high-level TTS processor functionality"""
    
    def setUp(self):
        self.processor = TTSProcessor(device="cpu")
    
    @patch.object(MeloTTSEngine, 'initialize')
    @patch.object(OpenVoiceCloner, 'initialize')
    def test_initialization(self, mock_voice_init, mock_melo_init):
        """Test TTS processor initialization"""
        self.processor.initialize()
        
        mock_melo_init.assert_called_once()
        mock_voice_init.assert_called_once()
    
    @patch.object(MeloTTSEngine, 'synthesize_to_file')
    @patch.object(OpenVoiceCloner, 'load_builtin_voice')
    @patch.object(OpenVoiceCloner, 'clone_voice')
    def test_synthesize_with_builtin_voice(self, mock_clone, mock_load_voice, mock_synthesize):
        """Test synthesis with built-in voice"""
        mock_synthesize.return_value = "temp_base.wav"
        mock_load_voice.return_value = torch.tensor([1, 2, 3])
        mock_clone.return_value = "output.wav"
        
        result = self.processor.synthesize_with_builtin_voice(
            "Hello world", "en-us", "output.wav"
        )
        
        self.assertEqual(result, "output.wav")
        mock_synthesize.assert_called_once()
        mock_load_voice.assert_called_once_with("en-us")
        mock_clone.assert_called_once()
    
    @patch.object(MeloTTSEngine, 'synthesize_to_file')
    def test_synthesize_base_only(self, mock_synthesize):
        """Test synthesis without voice cloning"""
        mock_synthesize.return_value = "output.wav"
        
        result = self.processor.synthesize_base_only("Hello", "output.wav", speed=1.2)
        
        self.assertEqual(result, "output.wav")
        mock_synthesize.assert_called_once_with(
            text="Hello",
            output_path="output.wav", 
            speed=1.2
        )
    
    @patch('app.services.tts_service.torch.zeros')
    @patch('app.services.tts_service.sf.write')
    def test_create_silence(self, mock_sf_write, mock_zeros):
        """Test silence creation"""
        mock_zeros.return_value = Mock()
        
        result = self.processor.create_silence("silence.wav", duration_seconds=2.5)
        
        self.assertEqual(result, "silence.wav")
        mock_zeros.assert_called_once_with(int(24000 * 2.5))
        mock_sf_write.assert_called_once()


class TestTTSIntegration(unittest.TestCase):
    """Integration tests for TTS components working together"""
    
    def setUp(self):
        self.processor = TTSProcessor(device="cpu")
    
    def test_full_pipeline_mock(self):
        """Test full TTS pipeline with mocked dependencies"""
        with patch.object(self.processor.melo_engine, 'synthesize_to_file') as mock_melo, \
             patch.object(self.processor.voice_cloner, 'extract_voice_from_audio') as mock_extract, \
             patch.object(self.processor.voice_cloner, 'clone_voice') as mock_clone:
            
            mock_melo.return_value = "temp_base.wav"
            mock_extract.return_value = torch.tensor([1, 2, 3])
            mock_clone.return_value = "final_output.wav"
            
            result = self.processor.synthesize_with_custom_voice(
                "[SPEED:fast] Hello world!",
                b"fake audio data",
                "wav",
                "output.wav"
            )
            
            self.assertEqual(result, "final_output.wav")
            
            # Verify the pipeline called all components
            mock_melo.assert_called_once()
            mock_extract.assert_called_once_with(b"fake audio data", "wav")
            mock_clone.assert_called_once()
    
    def test_error_propagation(self):
        """Test that errors propagate correctly through the pipeline"""
        with patch.object(self.processor.melo_engine, 'synthesize_to_file', 
                         side_effect=MeloTTSException("Test error")):
            
            with self.assertRaises(TTSException) as context:
                self.processor.synthesize_base_only("Hello", "output.wav")
            
            self.assertIn("Base TTS synthesis failed", str(context.exception))
            self.assertIn("Test error", str(context.exception))


if __name__ == '__main__':
    unittest.main()