import re
from typing import Tuple

class TextProcessor:
    """Handles text preprocessing and tag parsing for TTS"""

    @staticmethod
    def parse_note_text_tags(text: str) -> Tuple[str, str, float, float]:
        """
        Parse emotion, speed, and pitch tags from note text.

        Args:
            text: Input text with optional tags like [EMOTION:excited], [SPEED:fast], [PITCH:high]

        Returns:
            Tuple of (clean_text, emotion, speed, pitch)
        """
        # Default values
        emotion = "neutral"
        speed = 1.0
        pitch = 1.0

        # Extract emotion tags
        emotion_match = re.search(r'\[EMOTION:(excited|sad|angry|happy|neutral)\]', text, re.IGNORECASE)
        if emotion_match:
            emotion = emotion_match.group(1).lower()
            text = re.sub(r'\[EMOTION:[^\]]+\]', '', text, flags=re.IGNORECASE)

        # Extract speed tags
        speed_match = re.search(r'\[SPEED:(slow|normal|fast|[\d.]+)\]', text, re.IGNORECASE)
        if speed_match:
            speed_val = speed_match.group(1).lower()
            if speed_val == "slow":
                speed = 0.7
            elif speed_val == "fast":
                speed = 1.3
            elif speed_val == "normal":
                speed = 1.0
            else:
                try:
                    speed = float(speed_val)
                    speed = max(0.5, min(2.0, speed))  # Clamp between 0.5 and 2.0
                except ValueError:
                    speed = 1.0
            text = re.sub(r'\[SPEED:[^\]]+\]', '', text, flags=re.IGNORECASE)

        # Extract pitch tags
        pitch_match = re.search(r'\[PITCH:(low|normal|high|[\d.]+)\]', text, re.IGNORECASE)
        if pitch_match:
            pitch_val = pitch_match.group(1).lower()
            if pitch_val == "low":
                pitch = 0.8
            elif pitch_val == "high":
                pitch = 1.2
            elif pitch_val == "normal":
                pitch = 1.0
            else:
                try:
                    pitch = float(pitch_val)
                    pitch = max(0.5, min(2.0, pitch))
                except ValueError:
                    pitch = 1.0
            text = re.sub(r'\[PITCH:[^\]]+\]', '', text, flags=re.IGNORECASE)

        # Handle pause tags by converting to commas for natural pauses
        text = re.sub(r'\[PAUSE:(\d+)\]', lambda m: ',' * int(m.group(1)), text, flags=re.IGNORECASE)

        # Handle emphasis tags by capitalizing words
        text = re.sub(r'\[EMPHASIS:([^\]]+)\]', lambda m: m.group(1).upper(), text, flags=re.IGNORECASE)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text, emotion, speed, pitch
