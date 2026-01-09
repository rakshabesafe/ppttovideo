import os
import torch
import soundfile as sf
import sys
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

from .base import FishSpeechException

# Add fish-speech to python path if not installed as package
# Assuming we cloned it to project root /fish-speech
sys.path.append(os.path.abspath("fish-speech"))

class FishSpeechEngine:
    """
    Handles Fish Speech TTS synthesis using the local Fish Speech model (v1.5).
    """

    def __init__(self):
        self.checkpoint_path = os.getenv("FISH_SPEECH_CHECKPOINT_PATH", "checkpoints/fish-speech-1.5")
        self.device = os.getenv("FISH_SPEECH_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
        self.codec_config_name = os.getenv("FISH_SPEECH_CODEC_CONFIG", "firefly_gan_vq")
        self.llm_model = None
        self.decode_one_token = None
        self.codec_model = None

    def initialize(self) -> None:
        if self.llm_model is not None and self.codec_model is not None:
            return

        try:
            print(f"Initializing Fish Speech 1.5 from {self.checkpoint_path} on {self.device}...")

            # Import here to avoid issues if not available during class definition
            try:
                from fish_speech.models.text2semantic.inference import init_model as init_llm
                from fish_speech.models.vqgan.inference import load_model as load_codec
            except ImportError as e:
                # Fallback check for older structure if needed, or raise
                raise FishSpeechException(f"Failed to import fish_speech 1.5 modules: {e}")

            # 1. Load LLM (Text2Semantic)
            precision = torch.half if self.device == "cuda" else torch.float32

            # Checkpoint path for LLM is usually the dir containing config.json
            self.llm_model, self.decode_one_token = init_llm(
                Path(self.checkpoint_path),
                self.device,
                precision,
                compile=False
            )
            print("Fish Speech LLM initialized")

            # 2. Load Codec (VQGAN)
            # Codec checkpoint is usually inside the same dir or specified explicitly
            # For 1.5, default name is firefly-gan-vq-fsq-8x1024-21hz-generator.pth
            # But user might have a different file.
            # We assume it is in the checkpoint_path or we try to find it.

            codec_checkpoint = os.path.join(self.checkpoint_path, f"{self.codec_config_name}-fsq-8x1024-21hz-generator.pth")
            if not os.path.exists(codec_checkpoint):
                 # Try finding any .pth with generator in name?
                 # Or fall back to 'codec.pth' (older style)
                 candidates = [
                     os.path.join(self.checkpoint_path, "firefly-gan-vq-fsq-8x1024-21hz-generator.pth"),
                     os.path.join(self.checkpoint_path, "codec.pth"),
                 ]
                 for c in candidates:
                     if os.path.exists(c):
                         codec_checkpoint = c
                         break

            if not os.path.exists(codec_checkpoint):
                print(f"Warning: Codec checkpoint not found in {self.checkpoint_path}. Attempting to load anyway if Hydra handles it (unlikely).")

            self.codec_model = load_codec(
                config_name=self.codec_config_name,
                checkpoint_path=codec_checkpoint,
                device=self.device
            )
            print(f"Fish Speech Codec initialized with config {self.codec_config_name}")

        except Exception as e:
            raise FishSpeechException(f"Fish Speech initialization failed: {e}")

    def synthesize_to_file(self, text: str, output_path: str, speed: float = 1.0) -> str:
        """
        Synthesize speech to file using local inference.
        """
        if self.llm_model is None or self.codec_model is None:
            self.initialize()

        try:
            from fish_speech.models.text2semantic.inference import generate_long

            # Handle silence tag
            if text == "[SILENCE]" or not text.strip():
                # Get sample rate from codec model spec_transform
                sr = 44100
                if hasattr(self.codec_model, 'spec_transform') and hasattr(self.codec_model.spec_transform, 'sample_rate'):
                    sr = self.codec_model.spec_transform.sample_rate
                elif hasattr(self.codec_model, 'sample_rate'):
                    sr = self.codec_model.sample_rate

                silence = torch.zeros(int(sr))
                sf.write(output_path, silence.numpy(), sr)
                return output_path

            print(f"Synthesizing with Fish Speech S1: '{text[:50]}...'")

            # Step 1: Generate Semantic Tokens (Codes) from Text
            generator = generate_long(
                model=self.llm_model,
                device=self.device,
                decode_one_token=self.decode_one_token,
                text=text,
                num_samples=1,
                max_new_tokens=0,
                top_p=0.8,
                repetition_penalty=1.1,
                temperature=0.8,
                compile=False,
                iterative_prompt=True,
                chunk_length=300,
                prompt_text=None,
                prompt_tokens=None
            )

            codes = []
            for response in generator:
                if response.action == "sample":
                    codes.append(response.codes)
                elif response.action == "next":
                    break

            if not codes:
                raise FishSpeechException("No codes generated from text")

            full_codes = torch.cat(codes, dim=1) # [num_codebooks, total_seq_len]
            full_codes = full_codes.to(self.device).long()

            # Step 2: Decode Codes to Audio
            # For VQGAN (1.5), decode takes (indices, feature_lengths)
            # indices: [Batch, Codebooks, Time] ?
            # `inference.py` (vqgan): `indices = model.encode(audios, ...)[0][0]` (removes B, N?)
            # Wait, `model.encode` returns `[indices, ...]`
            # If `indices` from encode is [B, N, T], then `[0][0]` is [T]? No.
            # `inference.py` loads `npy` as 2D: [N, T].
            # Then calls `model.decode(indices=indices[None], feature_lengths=feature_lengths)`
            # `indices[None]` -> [1, N, T].
            # So `decode` expects 3D.

            feature_lengths = torch.tensor([full_codes.shape[1]], device=self.device, dtype=torch.long)

            fake_audios, _ = self.codec_model.decode(
                indices=full_codes.unsqueeze(0),
                feature_lengths=feature_lengths
            )

            # fake_audios: [Batch, Channels, Time] -> [1, 1, T]
            fake_audio = fake_audios[0, 0].float().cpu().numpy()

            # Get sample rate
            sr = 44100
            if hasattr(self.codec_model, 'spec_transform'):
                sr = self.codec_model.spec_transform.sample_rate

            sf.write(output_path, fake_audio, sr)

            return output_path

        except Exception as e:
            raise FishSpeechException(f"Fish Speech synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.llm_model is not None and self.codec_model is not None
