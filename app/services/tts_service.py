"""
TTS (Text-to-Speech) Service Components

This module now re-exports components from the modular `app.services.tts` package.
"""

from .tts.base import TTSException, MeloTTSException, OpenVoiceException, NeuphonicException
from .tts.text_processing import TextProcessor
from .tts.melo import MeloTTSEngine
from .tts.neuphonic import NeuphonicEngine
from .tts.openvoice import OpenVoiceCloner
from .tts.processor import TTSProcessor
