"""
Base Speech-to-Text interface.

Defines the abstract interface that all STT providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class STTProvider(ABC):
    """Abstract base class for STT providers."""

    @abstractmethod
    def transcribe(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert speech audio to text.

        Args:
            audio_data: Audio file data as bytes
            audio_format: Audio format (webm, mp3, wav, etc.)
            language: Optional language code (e.g., 'en', 'es')

        Returns:
            Dictionary with:
                - text: Transcribed text
                - language: Detected/used language code
                - confidence: Optional confidence score

        Raises:
            Exception: If transcription fails
        """
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Check if STT provider is available and working.

        Returns:
            Health status dictionary
        """
        pass
