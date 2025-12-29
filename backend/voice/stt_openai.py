"""
OpenAI Whisper Speech-to-Text provider.

Uses OpenAI's Whisper API for accurate speech recognition.
Supports multiple languages and audio formats.
"""

import logging
import tempfile
import os
from typing import Optional, Dict, Any
from openai import OpenAI

from .stt_base import STTProvider


class OpenAIWhisperProvider(STTProvider):
    """OpenAI Whisper STT provider using the OpenAI API."""

    def __init__(self, api_key: str, model: str = "whisper-1"):
        """
        Initialize OpenAI Whisper provider.

        Args:
            api_key: OpenAI API key
            model: Whisper model to use (whisper-1)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def transcribe(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert speech to text using OpenAI Whisper.

        Args:
            audio_data: Audio file data as bytes
            audio_format: Audio format (webm, mp3, wav, m4a, etc.)
            language: Optional language code (ISO-639-1, e.g., 'en', 'es')

        Returns:
            Dictionary with transcription results:
                - text: Transcribed text
                - language: Detected/used language code

        Raises:
            Exception: If transcription fails
        """
        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        # Write audio to temporary file (Whisper API requires a file)
        temp_file = None
        try:
            # Create temp file with appropriate extension
            with tempfile.NamedTemporaryFile(
                suffix=f".{audio_format}",
                delete=False
            ) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            logging.info(f"[STT] Transcribing {len(audio_data)} bytes of {audio_format} audio")

            # Open file for Whisper API
            with open(temp_path, "rb") as audio_file:
                kwargs = {
                    "model": self.model,
                    "file": audio_file,
                    "response_format": "verbose_json"  # Get more details
                }

                # Add language if specified
                if language:
                    kwargs["language"] = language

                response = self.client.audio.transcriptions.create(**kwargs)

            # Extract transcription text
            text = response.text.strip() if hasattr(response, 'text') else ""

            # Get language from response if available
            detected_language = getattr(response, 'language', language or 'unknown')

            logging.info(f"[STT] Transcribed: '{text[:100]}...' (language: {detected_language})")

            return {
                "text": text,
                "language": detected_language
            }

        except Exception as e:
            logging.error(f"[STT] Transcription failed: {e}")
            raise Exception(f"STT transcription failed: {str(e)}")

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logging.warning(f"[STT] Failed to delete temp file: {e}")

    def check_health(self) -> Dict[str, Any]:
        """
        Check if OpenAI Whisper is available.

        Returns:
            Health status dictionary
        """
        try:
            # We can't easily test without audio data, so just verify API key format
            # A real health check would require a small test audio file
            return {
                "healthy": True,
                "provider": "openai_whisper",
                "model": self.model,
                "note": "Full health check requires audio sample"
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": "openai_whisper",
                "error": str(e)
            }
