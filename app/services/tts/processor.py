import os
import time
import torch
import soundfile as sf
from typing import Optional

from .base import TTSException
from .text_processing import TextProcessor
from .melo import MeloTTSEngine
from .openvoice import OpenVoiceCloner
from .neuphonic import NeuphonicEngine
from .fishspeech import FishSpeechEngine
from .chatterbox import ChatterboxEngine

class TTSProcessor:
    """High-level TTS processor that orchestrates MeloTTS, OpenVoice, Neuphonic, Fish Speech and Chatterbox"""

    def __init__(self, device: str = None):
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.engine_type = os.getenv("TTS_ENGINE", "melotts").lower()
        self.melo_engine = MeloTTSEngine(device=self.device)
        self.voice_cloner = OpenVoiceCloner(device=self.device)
        self.neuphonic_engine = NeuphonicEngine()
        self.fish_engine = FishSpeechEngine()
        self.chatterbox_engine = ChatterboxEngine()
        self.text_processor = TextProcessor()
        print(f"TTS Processor initialized with engine: {self.engine_type}")

    def initialize(self) -> None:
        """Initialize the selected TTS engine components"""
        if self.engine_type == "neuphonic":
            self.neuphonic_engine.initialize()
        elif self.engine_type == "fishspeech":
            self.fish_engine.initialize()
        elif self.engine_type == "chatterbox":
            self.chatterbox_engine.initialize()
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

            if self.engine_type == "fishspeech":
                return self.fish_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=output_path,
                    speed=speed
                )

            if self.engine_type == "chatterbox":
                return self.chatterbox_engine.synthesize_to_file(
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

            if self.engine_type == "fishspeech":
                 raise NotImplementedError("Custom voice synthesis not yet implemented for Fish Speech engine")

            if self.engine_type == "chatterbox":
                 raise NotImplementedError("Custom voice synthesis not yet implemented for Chatterbox engine")

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

            if self.engine_type == "fishspeech":
                return self.fish_engine.synthesize_to_file(
                    text=clean_text,
                    output_path=output_path,
                    speed=actual_speed
                )

            if self.engine_type == "chatterbox":
                return self.chatterbox_engine.synthesize_to_file(
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
        if self.engine_type == "fishspeech":
            return self.fish_engine.is_initialized()
        if self.engine_type == "chatterbox":
            return self.chatterbox_engine.is_initialized()
        return self.melo_engine.is_initialized() and self.voice_cloner.is_initialized()
