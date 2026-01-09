class TTSException(Exception):
    """Base exception for TTS operations"""
    pass


class MeloTTSException(TTSException):
    """Exception specific to MeloTTS operations"""
    pass


class OpenVoiceException(TTSException):
    """Exception specific to OpenVoice operations"""
    pass


class NeuphonicException(TTSException):
    """Exception specific to Neuphonic operations"""
    pass


class FishSpeechException(TTSException):
    """Exception specific to Fish Speech operations"""
    pass


class ChatterboxException(TTSException):
    """Exception specific to Chatterbox operations"""
    pass
