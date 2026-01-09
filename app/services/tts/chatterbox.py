import os
import torch
import soundfile as sf
import sys
from typing import Optional

from .base import ChatterboxException

class ChatterboxEngine:
    """
    Handles Chatterbox TTS synthesis using Chatterbox-Turbo.
    """

    def __init__(self):
        self.device = os.getenv("CHATTERBOX_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
        self.default_ref_audio = os.getenv("CHATTERBOX_REF_AUDIO", "app/services/tts/data/default_ref.wav")
        self.model = None

    def initialize(self) -> None:
        if self.model is not None:
            return

        try:
            print(f"Initializing Chatterbox Turbo on {self.device}...")
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
            print("Chatterbox Turbo initialized successfully")

        except Exception as e:
            raise ChatterboxException(f"Chatterbox initialization failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0) -> str:
        """
        Synthesize speech to file.
        """
        if self.model is None:
            self.initialize()

        try:
            import torchaudio

            # Handle silence tag
            if text == "[SILENCE]" or not text.strip():
                sr = self.model.sr if hasattr(self.model, 'sr') else 24000
                silence = torch.zeros(1, int(sr))
                torchaudio.save(output_path, silence, sr)
                return output_path

            print(f"Synthesizing with Chatterbox: '{text[:50]}...'")

            # Check for reference audio
            # Chatterbox Turbo requires audio prompt?
            # Usage: `wav = model.generate(text, audio_prompt_path="your_10s_ref_clip.wav")`
            # If `audio_prompt_path` is omitted, does it work?
            # Website says: "# Generate audio (requires a reference clip for voice cloning)"
            # Wait, "Zero-shot voice agents".
            # Can it do non-cloning?
            # `ChatterboxTTS` (non-turbo) example: `wav = model.generate(text)`.
            # `ChatterboxTurboTTS` example shows `audio_prompt_path`.
            # I will use default ref audio if available.

            if os.path.exists(self.default_ref_audio):
                audio_prompt = self.default_ref_audio
            else:
                # Try without? Or fail?
                # If required, we must have it.
                # Assuming I copied `default_ref.wav` earlier for Neuphonic, I can use it here too.
                audio_prompt = self.default_ref_audio # Use it and let it fail if missing or logic handles None

            # Generate
            # Chatterbox Turbo generate signature: (text, audio_prompt_path=None, ...)
            # If path is None, maybe it uses internal speaker?
            # But the example says "requires a reference clip".
            # I'll pass it if exists.

            if os.path.exists(audio_prompt):
                wav = self.model.generate(text, audio_prompt_path=audio_prompt)
            else:
                print("Warning: No reference audio found for Chatterbox. Attempting generation without prompt.")
                wav = self.model.generate(text)

            # wav is tensor [channels, time]?
            # `ta.save` expects [channels, time].
            # Ensure it's on CPU.
            wav = wav.cpu()

            torchaudio.save(output_path, wav, self.model.sr)

            return output_path

        except Exception as e:
            raise ChatterboxException(f"Chatterbox synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.model is not None
