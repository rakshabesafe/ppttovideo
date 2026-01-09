import os
import torch
from typing import Optional

from .base import OpenVoiceException

# Import required libraries
se_extractor = None
ToneColorConverter = None

try:
    from openvoice import se_extractor
    from openvoice.api import ToneColorConverter
    print("OpenVoice imported successfully")
except ImportError as e:
    print(f"Warning: OpenVoice not available: {e}")


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
