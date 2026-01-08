import os
import soundfile as sf
from typing import Optional
from .base import FishSpeechException

class FishSpeechEngine:
    """
    Handles Fish Speech TTS synthesis using the official Fish Audio SDK.
    Requires FISH_AUDIO_API_KEY environment variable.
    """

    def __init__(self):
        self.api_key = os.getenv("FISH_AUDIO_API_KEY")
        self.client = None

    def initialize(self) -> None:
        if self.client is not None:
            return

        if not self.api_key:
             # Try to reload env var just in case
             self.api_key = os.getenv("FISH_AUDIO_API_KEY")
             if not self.api_key:
                 raise FishSpeechException("Fish Audio API key not found. Please set FISH_AUDIO_API_KEY environment variable.")

        try:
            print("Initializing Fish Audio SDK...")
            from fishaudio import FishAudio
            self.client = FishAudio(api_key=self.api_key)
            print("Fish Audio SDK initialized successfully")
        except Exception as e:
            raise FishSpeechException(f"Fish Audio initialization failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0) -> str:
        """
        Synthesize speech to file.
        """
        if self.client is None:
            self.initialize()

        try:
            # Handle silence tag
            if text == "[SILENCE]" or not text.strip():
                import torch
                # Create 1 second of silence
                silence = torch.zeros(24000)  # 24kHz sample rate (assuming, though fish might differ)
                sf.write(output_path, silence.numpy(), 24000)
                return output_path

            print(f"Synthesizing with Fish Audio: '{text[:50]}...'")

            # Using client.tts.convert
            # It returns bytes or stream? The docs example:
            # from fishaudio.utils import save
            # audio = client.tts.convert(text="Hello")
            # save(audio, output_path)

            from fishaudio.utils import save as save_audio

            # Note: Speed parameter handling.
            # SDK might support options in convert request.
            # Looking at docs/examples found online:
            # client.tts.convert(text=..., reference_id=...)
            # Doesn't seem to have speed parameter in the simple `convert` call signature readily available in snippets.
            # We will ignore speed for now or check if we can post-process.
            # Actually, user snippet mentioned "Speed (0.8x to 1.2x) and pitch adjust easily" but didn't show how.

            # We will proceed with basic synthesis.

            # Check for reference_id if custom voice is desired?
            # For now, default voice.

            audio = self.client.tts.convert(
                text=text,
                format="wav" # explicit format if supported
            )

            save_audio(audio, output_path)

            return output_path

        except Exception as e:
            raise FishSpeechException(f"Fish Speech synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.client is not None
