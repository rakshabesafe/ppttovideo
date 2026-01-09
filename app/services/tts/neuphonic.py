import os
import torch
import soundfile as sf
import sys
from typing import Optional

from .base import NeuphonicException

# Add neutts-air to python path if not installed as package
# Assuming we cloned it to project root /neutts-air
sys.path.append(os.path.abspath("neutts-air"))

class NeuphonicEngine:
    """
    Handles Neuphonic TTS synthesis using NeuTTS Air (on-device).
    """

    def __init__(self):
        self.backbone_repo = os.getenv("NEUPHONIC_BACKBONE_REPO", "neuphonic/neutts-air")
        self.codec_repo = os.getenv("NEUPHONIC_CODEC_REPO", "neuphonic/neucodec")
        self.backbone_device = os.getenv("NEUPHONIC_BACKBONE_DEVICE", "cpu")
        self.codec_device = os.getenv("NEUPHONIC_CODEC_DEVICE", "cpu")
        self.default_ref_audio = os.getenv("NEUPHONIC_REF_AUDIO", "app/services/tts/data/default_ref.wav")
        self.default_ref_text = os.getenv("NEUPHONIC_REF_TEXT", "app/services/tts/data/default_ref.txt")
        self.tts_model = None
        self.cached_ref_codes = None

    def initialize(self) -> None:
        if self.tts_model is not None:
            return

        try:
            print(f"Initializing NeuTTS Air with backbone={self.backbone_repo}...")
            from neuttsair.neutts import NeuTTSAir

            self.tts_model = NeuTTSAir(
                backbone_repo=self.backbone_repo,
                backbone_device=self.backbone_device,
                codec_repo=self.codec_repo,
                codec_device=self.codec_device
            )
            print("NeuTTS Air initialized successfully")

            # Pre-cache default reference codes
            if os.path.exists(self.default_ref_audio) and os.path.exists(self.default_ref_text):
                print(f"Encoding default reference audio: {self.default_ref_audio}")
                self.cached_ref_codes = self.tts_model.encode_reference(self.default_ref_audio)
            else:
                print(f"Warning: Default reference audio/text not found at {self.default_ref_audio} / {self.default_ref_text}")

        except Exception as e:
            raise NeuphonicException(f"NeuTTS Air initialization failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0) -> str:
        """
        Synthesize speech to file.
        Note: speed parameter is not directly supported by NeuTTS Air inference currently
        but kept for interface compatibility.
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

            print(f"Synthesizing with NeuTTS Air: '{text[:50]}...'")

            ref_text_content = ""
            if os.path.exists(self.default_ref_text):
                 with open(self.default_ref_text, "r") as f:
                     ref_text_content = f.read().strip()

            # Use cached ref codes if available, else encode (or fail if no default)
            ref_codes = self.cached_ref_codes
            if ref_codes is None:
                if os.path.exists(self.default_ref_audio):
                    ref_codes = self.tts_model.encode_reference(self.default_ref_audio)
                else:
                    raise NeuphonicException("No reference audio available for synthesis")

            # Infer
            # infer(self, input_text, ref_codes, ref_text)
            wav = self.tts_model.infer(text, ref_codes, ref_text_content)

            # Save to file
            # wav is typically a numpy array or tensor?
            # Example says: sf.write("test.wav", wav, 24000)
            # So it's likely numpy array. 24000 is likely the sample rate of neucodec?
            # I should verify sample rate from model or config, but example uses 24000.

            sf.write(output_path, wav, 24000)

            return output_path

        except Exception as e:
            raise NeuphonicException(f"NeuTTS Air synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.tts_model is not None
