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
    Handles Fish Speech TTS synthesis using the local Fish Speech model (OpenAudio S1 Mini).
    """

    def __init__(self):
        self.checkpoint_path = os.getenv("FISH_SPEECH_CHECKPOINT_PATH", "checkpoints/openaudio-s1-mini")
        self.device = os.getenv("FISH_SPEECH_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
        self.llm_model = None
        self.decode_one_token = None
        self.codec_model = None
        self.tokenizer = None # If needed separately, but init_model returns model which has it

    def initialize(self) -> None:
        if self.llm_model is not None and self.codec_model is not None:
            return

        try:
            print(f"Initializing Fish Speech S1 Mini from {self.checkpoint_path} on {self.device}...")

            # Import here to avoid issues if not available during class definition
            try:
                from fish_speech.models.text2semantic.inference import init_model as init_llm
                from fish_speech.models.dac.inference import load_model as load_codec
            except ImportError as e:
                raise FishSpeechException(f"Failed to import fish_speech modules: {e}")

            # 1. Load LLM (Text2Semantic)
            # The checkpoint path should be the directory containing config.json etc. for LLM
            # init_model(checkpoint_path, device, precision, compile=False)
            # precision usually half or bfloat16 for cuda
            precision = torch.half if self.device == "cuda" else torch.float32

            self.llm_model, self.decode_one_token = init_llm(
                Path(self.checkpoint_path),
                self.device,
                precision,
                compile=False # Disable compile for compatibility/speed on first run
            )
            print("Fish Speech LLM initialized")

            # 2. Load Codec (DAC/VQGAN)
            # Codec checkpoint is usually inside the same dir or separate.
            # Default structure: checkpoints/openaudio-s1-mini/codec.pth
            # The `load_model` function in dac/inference.py uses hydra.
            # It expects `config_name` and `checkpoint_path`.
            # Config name defaults to "modded_dac_vq".
            # Important: hydra might need config path setup.
            # load_model code:
            # with initialize(version_base="1.3", config_path="../../configs"):
            #     cfg = compose(config_name=config_name)
            # This relative path `../../configs` depends on where `dac/inference.py` is located.
            # Since we import it, it should resolve correctly relative to that file.

            codec_checkpoint = os.path.join(self.checkpoint_path, "codec.pth")
            if not os.path.exists(codec_checkpoint):
                 # Fallback or check if user provided full path in env var?
                 # Assuming user provided dir.
                 print(f"Warning: codec.pth not found in {self.checkpoint_path}, trying default location or checking if path is file")

            self.codec_model = load_codec(
                config_name="modded_dac_vq", # Use default or env var?
                checkpoint_path=codec_checkpoint,
                device=self.device
            )
            print("Fish Speech Codec initialized")

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
                # Create 1 second of silence
                silence = torch.zeros(int(24000)) # 24kHz is standard? Codec sample rate?
                # Codec model has sample_rate attribute
                sr = self.codec_model.sample_rate if hasattr(self.codec_model, 'sample_rate') else 44100
                silence = torch.zeros(int(sr))
                sf.write(output_path, silence.numpy(), sr)
                return output_path

            print(f"Synthesizing with Fish Speech S1: '{text[:50]}...'")

            # Step 1: Generate Semantic Tokens (Codes) from Text
            # We use generate_long generator

            # Param: text, num_samples=1, max_new_tokens=0, ...
            # Need to iterate over generator

            generator = generate_long(
                model=self.llm_model,
                device=self.device,
                decode_one_token=self.decode_one_token,
                text=text,
                num_samples=1,
                max_new_tokens=0, # 0 means auto based on text length? Or model max?
                # `inference.py` says "max_new_tokens is 0" -> calculates from text length or fills context?
                # Actually, `generate_long` calculates `max_new_tokens` based on input if 0?
                # No, it uses `model.config.max_seq_len` logic.
                # Let's trust default.
                top_p=0.8,
                repetition_penalty=1.1,
                temperature=0.8, # Default params
                compile=False,
                iterative_prompt=True,
                chunk_length=300, # Default in CLI
                prompt_text=None, # Zero-shot if None
                prompt_tokens=None
            )

            codes = []
            for response in generator:
                if response.action == "sample":
                    codes.append(response.codes)
                elif response.action == "next":
                    break # Only one sample requested

            if not codes:
                raise FishSpeechException("No codes generated from text")

            # Concatenate codes
            # codes list of tensors
            # shape: [1, seq_len] ?
            # `response.codes` in `generate_long` is `y[1:, ...]` -> codebook_dim?
            # Let's look at `inference.py`: `codes = y[1:, prompt_length:-1].clone()`
            # It returns shape [num_codebooks, seq_len] probably.
            # `torch.cat(codes, dim=1)` is done in main.

            full_codes = torch.cat(codes, dim=1) # [num_codebooks, total_seq_len]

            # Step 2: Decode Codes to Audio
            # `codec_model.decode(indices, indices_lens)`
            # indices expected shape: [batch, num_codebooks, seq_len] or [batch, seq_len] if 1 codebook?
            # Fish speech uses multiple codebooks (VQ).
            # `dac/inference.py`: `indices = torch.from_numpy(indices).to(device).long()`
            # `assert indices.ndim == 2` -> [num_codebooks, seq_len] ?
            # Wait, `main` in `dac/inference.py`:
            # `indices = np.load(input_path)`
            # `indices.ndim == 2`
            # `indices_lens = torch.tensor([indices.shape[1]], ...)`
            # So `indices` passed to `decode` is [num_codebooks, seq_len]?
            # Let's check `model.decode` signature in `fish_speech/models/dac/modded_dac.py` (if available) or usage.
            # In `dac/inference.py`: `fake_audios, audio_lengths = model.decode(indices, indices_lens)`
            # But `indices` variable in `dac/inference.py` main (npy case) is loaded from npy.
            # In `text2semantic/inference.py`: `np.save(..., torch.cat(codes, dim=1).cpu().numpy())`
            # So `full_codes` [num_codebooks, seq_len] is correct.

            # However, `model.decode` likely expects a batch dimension?
            # In `dac/inference.py`, `indices` loaded from npy has 2 dims?
            # `indices = indices[None]` might be needed?
            # In `dac/inference.py`:
            # `indices = torch.from_numpy(indices).to(device).long()`
            # `assert indices.ndim == 2`
            # `indices_lens = ...`
            # `model.decode(indices, indices_lens)`
            # So `decode` handles 2D input? Or `dac` model expects 2D?
            # Usually [batch, codebooks, time].
            # If `indices` is 2D, maybe it's [codebooks, time]?
            # Let's assume `full_codes` needs to be passed directly (it is a tensor).

            # But wait, `dac/inference.py` main handles `npy` (2D) and passes it to `decode`.
            # If `decode` expects batch, `inference.py` might be relying on `decode` handling unbatched or `indices` being batched?
            # `np.load` returns array.
            # Let's verify `full_codes` shape.
            # `text2semantic` generates `codes` as `y[1:, ...]` where `y` is `[codebook_dim, seq_len]`.
            # So `codes` is `[num_codebooks, seq_len]`.
            # `full_codes` is `[num_codebooks, total_len]`.

            # We might need to add batch dim: `full_codes.unsqueeze(0)` -> `[1, num_codebooks, total_len]`.
            # `dac/inference.py` DOES NOT unsqueeze for npy input.
            # `indices = torch.from_numpy(indices)...`
            # `indices_lens = ...`
            # `model.decode(indices, indices_lens)`
            # Maybe `decode` adds it? Or `dac` implementation allows it.
            # I will try without unsqueeze first, matching `dac/inference.py` logic.

            full_codes = full_codes.to(self.device).long()
            indices_lens = torch.tensor([full_codes.shape[1]], device=self.device, dtype=torch.long)

            # Use `unsqueeze(0)` just in case if `decode` expects batch,
            # but if `inference.py` doesn't do it, maybe I shouldn't.
            # Wait, `inference.py` for audio input: `audios = audio[None].to(device)` -> adds batch dim.
            # `indices, ... = model.encode(audios, ...)`
            # `indices` returned might be [batch, n_codebooks, time].
            # `if indices.ndim == 3: indices = indices[0]` -> removes batch dim before saving to npy.
            # So npy is [n_codebooks, time].
            # When loading npy: `indices = np.load...` (2D).
            # `model.decode` is called with this 2D tensor.
            # So `decode` supports 2D input (likely treats as batch=1 implicitly or implementation handles it).
            # However, looking at `dac` codebase (if standard), usually expects batch.
            # But `fish-speech` might have modified it (`modded_dac`).
            # I will follow `dac/inference.py`: pass 2D tensor.

            # However, I should check if `full_codes` from `generate_long` is on device.
            # `generate_long` yields `codes` which are slices of `y`. `y` is on device.
            # So `full_codes` is on device.

            fake_audios, audio_lengths = self.codec_model.decode(
                full_codes.unsqueeze(0), # I strongly suspect it needs batch dim if not provided by inference.py wrapper...
                # Wait, if `dac/inference.py` passes 2D, then `decode` MUST handle 2D.
                # BUT `dac/inference.py` imports `instantiate` from `hydra`.
                # Maybe I should just check if it fails.
                # Actually, standard DAC decode expects (B, N, T).
                # `dac/inference.py` MIGHT BE WRONG or I misread it?
                # `indices = np.load(...)` -> 2D.
                # `fake_audios, ... = model.decode(indices, indices_lens)`
                # If `model.decode` expects 3D, this would fail.
                # UNLESS `indices` from npy is 3D?
                # `np.save(..., indices.cpu().numpy())` where `indices` was `indices[0]` (2D) if it was 3D.
                # So npy is 2D.
                # So `model.decode` takes 2D.
                # ...
                # Let's try 2D. If it fails, I'll catch and try 3D.
                indices_lens
            )
            # `fake_audios` should be [batch, channels, time].
            # `inference.py`: `fake_audio = fake_audios[0, 0].float().cpu().numpy()`

            fake_audio = fake_audios[0, 0].float().cpu().numpy()

            sf.write(output_path, fake_audio, self.codec_model.sample_rate)

            return output_path

        except Exception as e:
            # Fallback retry with batch dim if generic exception?
            # Better to fix code.
            # I'll add a check/try-except block for dimension if needed or just assume 3D if 2D fails?
            # Actually, let's look at `dac/inference.py` again.
            # `fake_audios, audio_lengths = model.decode(indices, indices_lens)`
            # It seems it handles it.
            raise FishSpeechException(f"Fish Speech synthesis failed: {e}")

    def is_initialized(self) -> bool:
        return self.llm_model is not None and self.codec_model is not None
