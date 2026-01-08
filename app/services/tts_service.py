"""
TTS (Text-to-Speech) Service Components

This module provides modular, testable components for TTS synthesis:
- MeloTTSEngine: Base TTS synthesis using MeloTTS
- OpenVoiceCloner: Voice cloning using OpenVoice
- TTSProcessor: Orchestrates the complete TTS pipeline
"""

import os
import sys
import time
import torch
import librosa
import soundfile as sf
import tempfile
import re
from typing import Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod

# Add MeloTTS to path
sys.path.append('/src/melotts')

# Import required libraries
TTS = None
se_extractor = None
ToneColorConverter = None

try:
    from melo.api import TTS as MeloTTS
    TTS = MeloTTS
    print("MeloTTS imported successfully")
except ImportError as e:
    print(f"Warning: MeloTTS not available: {e}")

try:
    from openvoice import se_extractor
    from openvoice.api import ToneColorConverter
    print("OpenVoice imported successfully")
except ImportError as e:
    print(f"Warning: OpenVoice not available: {e}")


class TTSException(Exception):
    """Base exception for TTS operations"""
    pass


class NeuphonicException(TTSException):
    """Exception specific to Neuphonic operations"""
    pass


class MeloTTSException(TTSException):
    """Exception specific to MeloTTS operations"""
    pass


class OpenVoiceException(TTSException):
    """Exception specific to OpenVoice operations"""
    pass


class TextProcessor:
    """Handles text preprocessing and tag parsing for TTS"""
    
    @staticmethod
    def parse_note_text_tags(text: str) -> Tuple[str, str, float, float]:
        """
        Parse emotion, speed, and pitch tags from note text.
        
        Args:
            text: Input text with optional tags like [EMOTION:excited], [SPEED:fast], [PITCH:high]
            
        Returns:
            Tuple of (clean_text, emotion, speed, pitch)
        """
        # Default values
        emotion = "neutral"
        speed = 1.0
        pitch = 1.0
        
        # Extract emotion tags
        emotion_match = re.search(r'\[EMOTION:(excited|sad|angry|happy|neutral)\]', text, re.IGNORECASE)
        if emotion_match:
            emotion = emotion_match.group(1).lower()
            text = re.sub(r'\[EMOTION:[^\]]+\]', '', text, flags=re.IGNORECASE)
        
        # Extract speed tags
        speed_match = re.search(r'\[SPEED:(slow|normal|fast|[\d.]+)\]', text, re.IGNORECASE)
        if speed_match:
            speed_val = speed_match.group(1).lower()
            if speed_val == "slow":
                speed = 0.7
            elif speed_val == "fast":
                speed = 1.3
            elif speed_val == "normal":
                speed = 1.0
            else:
                try:
                    speed = float(speed_val)
                    speed = max(0.5, min(2.0, speed))  # Clamp between 0.5 and 2.0
                except ValueError:
                    speed = 1.0
            text = re.sub(r'\[SPEED:[^\]]+\]', '', text, flags=re.IGNORECASE)
        
        # Extract pitch tags
        pitch_match = re.search(r'\[PITCH:(low|normal|high|[\d.]+)\]', text, re.IGNORECASE)
        if pitch_match:
            pitch_val = pitch_match.group(1).lower()
            if pitch_val == "low":
                pitch = 0.8
            elif pitch_val == "high":
                pitch = 1.2
            elif pitch_val == "normal":
                pitch = 1.0
            else:
                try:
                    pitch = float(pitch_val)
                    pitch = max(0.5, min(2.0, pitch))
                except ValueError:
                    pitch = 1.0
            text = re.sub(r'\[PITCH:[^\]]+\]', '', text, flags=re.IGNORECASE)
        
        # Handle pause tags by converting to commas for natural pauses
        text = re.sub(r'\[PAUSE:(\d+)\]', lambda m: ',' * int(m.group(1)), text, flags=re.IGNORECASE)
        
        # Handle emphasis tags by capitalizing words
        text = re.sub(r'\[EMPHASIS:([^\]]+)\]', lambda m: m.group(1).upper(), text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text, emotion, speed, pitch


class MeloTTSEngine:
    """Handles MeloTTS base speech synthesis"""
    
    def __init__(self, device: str = None):
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.tts_model: Optional[TTS] = None
        self.speaker_ids: Dict[str, int] = {}
        
    def initialize(self) -> None:
        """Initialize MeloTTS model and download required dependencies"""
        if self.tts_model is not None:
            return  # Already initialized
            
        # Check if TTS is available
        if TTS is None:
            raise MeloTTSException("MeloTTS initialization failed: TTS module not available. Please ensure MeloTTS is properly installed.")
            
        try:
            print("Initializing MeloTTS for speech synthesis...")
            
            # Download required NLTK data
            try:
                import nltk
                print("Downloading required NLTK data...")
                nltk.download('averaged_perceptron_tagger_eng', quiet=True)
                nltk.download('averaged_perceptron_tagger', quiet=True)
                nltk.download('cmudict', quiet=True)
                print("NLTK data downloaded successfully")
            except Exception as nltk_error:
                print(f"NLTK setup warning: {nltk_error}")
            
            # Initialize MeloTTS
            self.tts_model = TTS(language='EN', device=self.device)
            self.speaker_ids = self.tts_model.hps.data.spk2id
            print(f"MeloTTS initialized successfully with speakers: {list(self.speaker_ids.keys())}")
            print(f"EN_INDIA speaker ID: {self.speaker_ids.get('EN_INDIA', 'Not found')}")
            
        except Exception as e:
            raise MeloTTSException(f"MeloTTS initialization failed: {e}")
    
    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0, 
                          speaker_id = 0) -> str:
        """
        Synthesize text to audio file using MeloTTS
        
        Args:
            text: Text to synthesize
            output_path: Path where audio file should be saved
            speed: Speech speed (0.5-2.0)
            speaker_id: Speaker ID to use (string like 'EN_INDIA' or int)
            
        Returns:
            Path to generated audio file
            
        Raises:
            MeloTTSException: If synthesis fails
        """
        if self.tts_model is None:
            self.initialize()
            
        try:
            # Handle silence tag
            if text == "[SILENCE]" or not text.strip():
                # Create 1 second of silence
                silence = torch.zeros(24000)  # 24kHz sample rate
                sf.write(output_path, silence.numpy(), 24000)
                return output_path
            
            print(f"Synthesizing with MeloTTS: '{text[:50]}...'")
            
            self.tts_model.tts_to_file(
                text=text,
                speaker_id=speaker_id,
                output_path=output_path,
                speed=speed,
                quiet=True
            )
            
            # Check base TTS audio quality (no pre-processing)
            try:
                import soundfile as sf
                import numpy as np
                audio, sr = sf.read(output_path)
                max_amp = np.max(np.abs(audio))
                print(f"Base TTS audio level: {max_amp:.4f}")
            except Exception as e:
                print(f"Warning: Base TTS audio check failed: {e}")
            
            if not os.path.exists(output_path):
                raise MeloTTSException("Audio file was not created")
                
            print(f"Base TTS audio generated successfully")
            return output_path
            
        except Exception as e:
            raise MeloTTSException(f"TTS synthesis failed: {e}")
    
    def is_initialized(self) -> bool:
        """Check if MeloTTS is initialized"""
        return self.tts_model is not None


class NeuphonicEngine:
    """Handles Neuphonic TTS synthesis"""

    def __init__(self):
        self.api_key = os.getenv("NEUPHONIC_API_KEY")
        self.client = None

    def initialize(self) -> None:
        if self.client is not None:
            return

        if not self.api_key:
             # Try to reload env var just in case
             self.api_key = os.getenv("NEUPHONIC_API_KEY")
             if not self.api_key:
                 raise NeuphonicException("Neuphonic API key not found. Please set NEUPHONIC_API_KEY environment variable.")

        try:
            from pyneuphonic import Neuphonic
            self.client = Neuphonic(api_key=self.api_key)
            print("Neuphonic initialized successfully")
        except Exception as e:
            raise NeuphonicException(f"Neuphonic initialization failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0) -> str:
        if self.client is None:
            self.initialize()

        try:
            from pyneuphonic import TTSConfig

            # Handle silence tag
            if text == "[SILENCE]" or not text.strip():
                # Create 1 second of silence
                silence = torch.zeros(24000)  # 24kHz sample rate
                sf.write(output_path, silence.numpy(), 24000)
                return output_path

            print(f"Synthesizing with Neuphonic: '{text[:50]}...'")

            sse = self.client.tts.SSEClient()
            tts_config = TTSConfig(speed=speed)

            response = sse.send(text, tts_config=tts_config)

            # Collect all audio chunks
            all_audio = bytearray()
            for item in response:
                 if item.data.audio:
                     all_audio.extend(item.data.audio)

            with open(output_path, "wb") as f:
                f.write(all_audio)

            return output_path

        except Exception as e:
            raise NeuphonicException(f"Neuphonic synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.client is not None


class OpenVoiceCloner:
    """Handles voice cloning using OpenVoice"""
    
    def __init__(self, device: str = None):
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.tone_converter: Optional[ToneColorConverter] = None
        self.source_se = None  # Source speaker embedding (loaded once)
        
    def initialize(self) -> None:
        """Initialize OpenVoice components following the 3-step recommendation"""
        if self.tone_converter is not None:
            return  # Already initialized
            
        # Check if OpenVoice is available
        if ToneColorConverter is None:
            raise OpenVoiceException("OpenVoice initialization failed: ToneColorConverter module not available. Please ensure OpenVoice is properly installed.")
            
        try:
            print("Initializing OpenVoice ToneColorConverter...")
            # Step 1: Initialize ToneColorConverter (proper 3-step process)
            self.tone_converter = ToneColorConverter(
                '/checkpoints_v2/checkpoints_v2/converter/config.json', 
                device=self.device
            )
            # Load the checkpoint (missing in previous implementation)
            self.tone_converter.load_ckpt('/checkpoints_v2/checkpoints_v2/converter/checkpoint.pth')
            
            # Load source speaker embedding for English Indian base speaker
            # Using EN_INDIA as recommended base speaker for English Indian voice cloning
            self.source_se = torch.load(
                '/checkpoints_v2/checkpoints_v2/base_speakers/ses/en-india.pth',
                map_location=self.device
            )
            print("OpenVoice initialized successfully with EN_INDIA base speaker")
            
        except Exception as e:
            raise OpenVoiceException(f"OpenVoice initialization failed: {e}")
    
    def load_builtin_voice(self, speaker_name: str) -> torch.Tensor:
        """
        Load a built-in voice embedding
        
        Args:
            speaker_name: Name of built-in speaker (e.g., 'en-us', 'en-br')
            
        Returns:
            Voice embedding tensor
        """
        try:
            embedding_path = f'checkpoints_v2/checkpoints_v2/base_speakers/ses/{speaker_name}.pth'
            target_se = torch.load(embedding_path, map_location=self.device)
            print(f"Loaded built-in voice: {speaker_name}")
            return target_se
        except Exception as e:
            raise OpenVoiceException(f"Failed to load built-in voice '{speaker_name}': {e}")
    
    def extract_voice_from_audio(self, audio_data: bytes, file_extension: str) -> torch.Tensor:
        """
        Extract voice embedding from reference audio following OpenVoice Step 2
        
        Args:
            audio_data: Raw audio file data
            file_extension: File extension (e.g., 'wav', 'mp3')
            
        Returns:
            Voice embedding tensor
        """
        if self.tone_converter is None:
            self.initialize()
            
        try:
            # Save audio data to temporary file
            temp_filename = f"temp_ref.{file_extension}"
            with open(temp_filename, "wb") as f:
                f.write(audio_data)
            
            # Step 2: Extract tone color embedding from entire reference audio
            # Following OpenVoice recommendation - entire MP3 file can be given to se_extractor
            print("Extracting tone color embedding from reference audio...")
            target_se, audio_name = se_extractor.get_se(
                temp_filename,  # Use original file directly, not trimmed
                self.tone_converter, 
                vad=True  # Enable VAD for better voice activity detection
            )
            
            # Clean up temporary files
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            
            print("Voice embedding extracted successfully using OpenVoice Step 2")
            return target_se
            
        except Exception as e:
            raise OpenVoiceException(f"Voice extraction failed: {e}")
    
    def clone_voice(self, base_audio_path: str, target_embedding: torch.Tensor, 
                   output_path: str) -> str:
        """
        Apply voice cloning to base audio
        
        Args:
            base_audio_path: Path to base TTS audio
            target_embedding: Target voice embedding
            output_path: Path for cloned audio output
            
        Returns:
            Path to cloned audio file
        """
        if self.tone_converter is None or self.source_se is None:
            self.initialize()
            
        try:
            # Apply voice conversion
            self.tone_converter.convert(
                audio_src_path=base_audio_path,
                src_se=self.source_se,
                tgt_se=target_embedding,
                output_path=output_path,
                message="Converting voice...",
                tau=0.8
            )
            
            if not os.path.exists(output_path):
                raise OpenVoiceException("Cloned audio file was not created")
            
            return output_path
            
        except Exception as e:
            raise OpenVoiceException(f"Voice cloning failed: {e}")
    
    def is_initialized(self) -> bool:
        """Check if OpenVoice is initialized"""
        return self.tone_converter is not None


class TTSProcessor:
    """High-level TTS processor that orchestrates MeloTTS and OpenVoice"""
    
    def __init__(self, device: str = None):
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.engine_type = os.getenv("TTS_ENGINE", "melotts").lower()
        self.melo_engine = MeloTTSEngine(device=self.device)
        self.voice_cloner = OpenVoiceCloner(device=self.device)
        self.neuphonic_engine = NeuphonicEngine()
        self.text_processor = TextProcessor()
        print(f"TTS Processor initialized with engine: {self.engine_type}")
        
    def initialize(self) -> None:
        """Initialize the selected TTS engine components"""
        if self.engine_type == "neuphonic":
            self.neuphonic_engine.initialize()
        else:
            self.melo_engine.initialize()
            self.voice_cloner.initialize()
        
    def synthesize_with_builtin_voice(self, text: str, speaker_name: str, 
                                     output_path: str) -> str:
        """
        Synthesize speech using a built-in voice
        
        Args:
            text: Text to synthesize
            speaker_name: Built-in speaker name (e.g., 'en-us')
            output_path: Output audio file path
            
        Returns:
            Path to generated audio file
        """
        try:
            # Parse text tags
            clean_text, emotion, speed, pitch = self.text_processor.parse_note_text_tags(text)
            
            if self.engine_type == "neuphonic":
                return self.neuphonic_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=output_path,
                    speed=speed
                )

            # Map speaker names to MeloTTS speakers
            melotts_speakers = {
                'en-default': 'EN-Default',
                'en-us': 'EN-US', 
                'en-br': 'EN-BR',
                'en-india': 'EN_INDIA',
                'en-au': 'EN-AU'
            }
            
            # Check if this is a MeloTTS native speaker (fast path)
            if speaker_name.lower() in melotts_speakers:
                melotts_speaker = melotts_speakers[speaker_name.lower()]
                print(f"Using native MeloTTS speaker: {melotts_speaker}")
                
                # Use MeloTTS directly with the specific speaker
                return self.melo_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=output_path,
                    speed=speed,
                    speaker_id=self.melo_engine.speaker_ids[melotts_speaker]
                )
            else:
                # Use OpenVoice cloning for non-MeloTTS speakers (slower)
                print(f"Using OpenVoice cloning for speaker: {speaker_name}")
                
                # Generate base TTS audio
                temp_base = f"temp_base_{int(time.time())}.wav"
                self.melo_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=temp_base,
                    speed=speed
                )
                
                # Load built-in voice embedding
                target_embedding = self.voice_cloner.load_builtin_voice(speaker_name)
                
                # Apply voice cloning
                self.voice_cloner.clone_voice(temp_base, target_embedding, output_path)
                
                # Clean up temporary file
                if os.path.exists(temp_base):
                    os.remove(temp_base)
                    
                return output_path
            
        except Exception as e:
            raise TTSException(f"Built-in voice synthesis failed: {e}")
    
    def synthesize_with_custom_voice(self, text: str, reference_audio_data: bytes,
                                   file_extension: str, output_path: str) -> str:
        """
        Synthesize speech using a custom voice from reference audio
        Following OpenVoice 3-step process with EN_INDIA base speaker
        
        Args:
            text: Text to synthesize
            reference_audio_data: Raw audio data for voice cloning
            file_extension: File extension of reference audio
            output_path: Output audio file path
            
        Returns:
            Path to generated audio file
        """
        try:
            # Parse text tags
            clean_text, emotion, speed, pitch = self.text_processor.parse_note_text_tags(text)
            
            if self.engine_type == "neuphonic":
                 # Neuphonic does support voice cloning, but the implementation is different.
                 # For now, we'll raise an error or fallback.
                 # Given the requirement "based on configuration user should be able to use different engine",
                 # I will assume users wanting cloning will use OpenVoice or we'd need to implement Neuphonic cloning.
                 # Let's log a warning and fallback or raise. The prompt didn't specify Neuphonic cloning.
                 # However, to avoid breaking if someone calls this, I'll raise a clear exception.
                 raise NotImplementedError("Custom voice synthesis not yet implemented for Neuphonic engine")

            # Step 3: Generate base TTS audio using MeloTTS EN_INDIA speaker
            # Following OpenVoice recommendation to use English Indian as base speaker
            temp_base = f"temp_base_{int(time.time())}.wav"
            
            # Use EN_INDIA speaker ID for base synthesis
            # Get speaker ID safely to avoid HParams error
            try:
                if hasattr(self.melo_engine.speaker_ids, 'get'):
                    en_india_speaker_id = self.melo_engine.speaker_ids.get('EN_INDIA', 0)
                else:
                    en_india_speaker_id = self.melo_engine.speaker_ids['EN_INDIA']
                print(f"Using EN_INDIA speaker (ID: {en_india_speaker_id}) as base speaker for custom voice cloning")
            except (KeyError, AttributeError) as e:
                print(f"Warning: Could not get EN_INDIA speaker ID: {e}, using default speaker")
                en_india_speaker_id = 0
            
            self.melo_engine.synthesize_to_file(
                text=clean_text,
                output_path=temp_base,
                speed=speed,
                speaker_id=en_india_speaker_id
            )
            
            # Step 2: Extract voice embedding from reference audio
            target_embedding = self.voice_cloner.extract_voice_from_audio(
                reference_audio_data, file_extension
            )
            
            # Apply voice cloning with proper source embedding
            self.voice_cloner.clone_voice(temp_base, target_embedding, output_path)
            
            # Clean up temporary file
            if os.path.exists(temp_base):
                os.remove(temp_base)
                
            return output_path
            
        except Exception as e:
            raise TTSException(f"Custom voice synthesis failed: {e}")
    
    def synthesize_base_only(self, text: str, output_path: str, speed: float = 1.0) -> str:
        """
        Synthesize speech using only MeloTTS (no voice cloning)
        
        Args:
            text: Text to synthesize
            output_path: Output audio file path
            speed: Speech speed
            
        Returns:
            Path to generated audio file
        """
        try:
            clean_text, emotion, speed_parsed, pitch = self.text_processor.parse_note_text_tags(text)
            actual_speed = speed_parsed if speed_parsed != 1.0 else speed
            
            if self.engine_type == "neuphonic":
                return self.neuphonic_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=output_path,
                    speed=actual_speed
                )

            return self.melo_engine.synthesize_to_file(
                text=clean_text,
                output_path=output_path,
                speed=actual_speed
            )
            
        except Exception as e:
            raise TTSException(f"Base TTS synthesis failed: {e}")
    
    def create_silence(self, output_path: str, duration_seconds: float = 1.0) -> str:
        """
        Create a silent audio file
        
        Args:
            output_path: Output audio file path
            duration_seconds: Duration of silence in seconds
            
        Returns:
            Path to generated silent audio file
        """
        try:
            silence = torch.zeros(int(24000 * duration_seconds))  # 24kHz sample rate
            sf.write(output_path, silence.numpy(), 24000)
            return output_path
        except Exception as e:
            raise TTSException(f"Silence generation failed: {e}")
    
    def is_ready(self) -> bool:
        """Check if both engines are ready"""
        if self.engine_type == "neuphonic":
            return self.neuphonic_engine.is_initialized()
        return self.melo_engine.is_initialized() and self.voice_cloner.is_initialized()