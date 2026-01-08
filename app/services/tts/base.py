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
