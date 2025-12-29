"""
Base Text-to-Speech interface.

Defines the abstract interface that all TTS providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_format: str = "mp3"
    ) -> bytes:
        """
        Convert text to speech audio.

        Args:
            text: Text to convert to speech
            voice: Voice ID/name to use (provider-specific)
            speed: Speech speed (0.25 to 4.0, default 1.0)
            output_format: Audio format (mp3, wav, etc.)

        Returns:
            Audio data as bytes

        Raises:
            Exception: If synthesis fails
        """
        pass

    @abstractmethod
    def list_voices(self) -> List[Dict[str, Any]]:
        """
        List available voices.

        Returns:
            List of voice dictionaries with metadata
        """
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Check if TTS provider is available and working.

        Returns:
            Health status dictionary
        """
        pass
