"""
OpenAI Text-to-Speech provider.

Uses OpenAI's TTS API for high-quality speech synthesis.
Supports multiple voices: alloy, echo, fable, onyx, nova, shimmer
"""

import logging
from typing import Optional, List, Dict, Any
from openai import OpenAI

from .tts_base import TTSProvider


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider using the OpenAI API."""

    # Available voices with descriptions
    VOICES = [
        {"id": "alloy", "name": "Alloy", "description": "Neutral, balanced voice"},
        {"id": "echo", "name": "Echo", "description": "Male, clear and articulate"},
        {"id": "fable", "name": "Fable", "description": "Male, warm and friendly"},
        {"id": "onyx", "name": "Onyx", "description": "Male, deep and authoritative"},
        {"id": "nova", "name": "Nova", "description": "Female, energetic and engaging"},
        {"id": "shimmer", "name": "Shimmer", "description": "Female, soft and gentle"},
    ]

    def __init__(self, api_key: str, model: str = "tts-1"):
        """
        Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key
            model: TTS model to use (tts-1 or tts-1-hd)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.default_voice = "alloy"

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_format: str = "mp3"
    ) -> bytes:
        """
        Convert text to speech using OpenAI TTS.

        Args:
            text: Text to convert to speech
            voice: Voice ID (alloy, echo, fable, onyx, nova, shimmer)
            speed: Speech speed (0.25 to 4.0, default 1.0)
            output_format: Audio format (mp3, opus, aac, flac, wav, pcm)

        Returns:
            Audio data as bytes

        Raises:
            Exception: If synthesis fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Validate voice
        selected_voice = voice or self.default_voice
        valid_voices = [v["id"] for v in self.VOICES]
        if selected_voice not in valid_voices:
            logging.warning(f"[TTS] Invalid voice '{selected_voice}', using default '{self.default_voice}'")
            selected_voice = self.default_voice

        # Validate speed
        speed = max(0.25, min(4.0, speed))

        # Validate format
        valid_formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
        if output_format not in valid_formats:
            logging.warning(f"[TTS] Invalid format '{output_format}', using mp3")
            output_format = "mp3"

        try:
            logging.info(f"[TTS] Synthesizing {len(text)} chars with voice '{selected_voice}', speed {speed}")

            response = self.client.audio.speech.create(
                model=self.model,
                voice=selected_voice,
                input=text,
                speed=speed,
                response_format=output_format
            )

            # Convert response to bytes
            audio_bytes = response.read()

            logging.info(f"[TTS] Generated {len(audio_bytes)} bytes of audio")
            return audio_bytes

        except Exception as e:
            logging.error(f"[TTS] Synthesis failed: {e}")
            raise Exception(f"TTS synthesis failed: {str(e)}")

    def list_voices(self) -> List[Dict[str, Any]]:
        """
        List available OpenAI voices.

        Returns:
            List of voice dictionaries
        """
        return self.VOICES.copy()

    def check_health(self) -> Dict[str, Any]:
        """
        Check if OpenAI TTS is available.

        Returns:
            Health status dictionary
        """
        try:
            # Try a minimal synthesis to verify API key and connectivity
            test_audio = self.synthesize("test", voice="alloy", speed=1.0)

            return {
                "healthy": True,
                "provider": "openai_tts",
                "model": self.model,
                "voices_available": len(self.VOICES),
                "test_audio_size": len(test_audio)
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": "openai_tts",
                "error": str(e)
            }
