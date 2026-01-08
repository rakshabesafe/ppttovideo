import os
import torch
import soundfile as sf
from .base import NeuphonicException

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
