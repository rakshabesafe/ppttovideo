import os
import sys
import torch
import soundfile as sf
import numpy as np
from typing import Optional, Dict

from .base import MeloTTSException

# Add MeloTTS to path
sys.path.append('/src/melotts')

TTS = None
try:
    from melo.api import TTS as MeloTTS
    TTS = MeloTTS
    print("MeloTTS imported successfully")
except ImportError as e:
    print(f"Warning: MeloTTS not available: {e}")

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
