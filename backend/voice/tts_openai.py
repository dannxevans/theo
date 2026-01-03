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

    def _chunk_text(self, text: str, max_length: int = 4000) -> List[str]:
        """
        Split text into chunks that respect sentence boundaries.

        Args:
            text: Text to split
            max_length: Maximum characters per chunk (default 4000, leaving buffer for 4096 limit)

        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        # Split on sentence boundaries (period, question mark, exclamation)
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in '.!?\n' and len(current_sentence.strip()) > 0:
                sentences.append(current_sentence)
                current_sentence = ""

        # Add any remaining text
        if current_sentence.strip():
            sentences.append(current_sentence)

        # Group sentences into chunks
        current_chunk = ""
        for sentence in sentences:
            # If single sentence exceeds max_length, split it
            if len(sentence) > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split long sentence by words
                words = sentence.split()
                word_chunk = ""
                for word in words:
                    if len(word_chunk) + len(word) + 1 <= max_length:
                        word_chunk += (" " if word_chunk else "") + word
                    else:
                        if word_chunk:
                            chunks.append(word_chunk)
                        word_chunk = word
                if word_chunk:
                    chunks.append(word_chunk)
            elif len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence
            else:
                chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_format: str = "mp3"
    ) -> bytes:
        """
        Convert text to speech using OpenAI TTS.
        Automatically chunks text longer than 4096 characters.

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
            # Check if text needs chunking
            if len(text) > 4000:
                logging.info(f"[TTS] Text length {len(text)} exceeds limit, chunking into smaller parts")
                chunks = self._chunk_text(text, max_length=4000)
                logging.info(f"[TTS] Split into {len(chunks)} chunks")

                # Synthesize each chunk
                audio_chunks = []
                for i, chunk in enumerate(chunks):
                    logging.info(f"[TTS] Synthesizing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")

                    response = self.client.audio.speech.create(
                        model=self.model,
                        voice=selected_voice,
                        input=chunk,
                        speed=speed,
                        response_format=output_format
                    )

                    audio_chunks.append(response.read())

                # Concatenate audio chunks
                audio_bytes = b''.join(audio_chunks)
                logging.info(f"[TTS] Generated {len(audio_bytes)} bytes of audio from {len(chunks)} chunks")
                return audio_bytes
            else:
                # Single request for short text
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

    def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_format: str = "mp3"
    ):
        """
        Stream audio chunks as they're generated by OpenAI TTS.
        Enables progressive audio playback starting within 2-3 seconds.

        Args:
            text: Text to convert to speech
            voice: Voice ID (alloy, echo, fable, onyx, nova, shimmer)
            speed: Speech speed (0.25 to 4.0, default 1.0)
            output_format: Audio format (mp3, opus, aac, flac, wav, pcm)

        Yields:
            bytes: Audio chunks as they arrive from OpenAI

        Raises:
            Exception: If synthesis fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Validate voice
        selected_voice = voice or self.default_voice
        valid_voices = [v["id"] for v in self.VOICES]
        if selected_voice not in valid_voices:
            logging.warning(f"[TTS STREAM] Invalid voice '{selected_voice}', using default '{self.default_voice}'")
            selected_voice = self.default_voice

        # Validate speed
        speed = max(0.25, min(4.0, speed))

        # Validate format
        valid_formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
        if output_format not in valid_formats:
            logging.warning(f"[TTS STREAM] Invalid format '{output_format}', using mp3")
            output_format = "mp3"

        try:
            # Check if text needs chunking
            if len(text) > 4000:
                logging.info(f"[TTS STREAM] Text length {len(text)} exceeds limit, chunking into smaller parts")
                chunks = self._chunk_text(text, max_length=4000)
                logging.info(f"[TTS STREAM] Split into {len(chunks)} chunks")

                # Stream each text chunk's audio
                for i, chunk in enumerate(chunks):
                    logging.info(f"[TTS STREAM] Streaming chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")

                    # Use with_streaming_response for proper streaming
                    with self.client.audio.speech.with_streaming_response.create(
                        model=self.model,
                        voice=selected_voice,
                        input=chunk,
                        speed=speed,
                        response_format=output_format
                    ) as response:
                        # Stream the response in 4KB chunks
                        chunk_size = 4096
                        for audio_chunk in response.iter_bytes(chunk_size=chunk_size):
                            yield audio_chunk

            else:
                # Single text, stream the audio response
                logging.info(f"[TTS STREAM] Streaming {len(text)} chars with voice '{selected_voice}', speed {speed}")

                # Use with_streaming_response for proper streaming
                with self.client.audio.speech.with_streaming_response.create(
                    model=self.model,
                    voice=selected_voice,
                    input=text,
                    speed=speed,
                    response_format=output_format
                ) as response:
                    # Stream the response in 4KB chunks
                    chunk_size = 4096
                    total_bytes = 0
                    for audio_chunk in response.iter_bytes(chunk_size=chunk_size):
                        total_bytes += len(audio_chunk)
                        yield audio_chunk

                    logging.info(f"[TTS STREAM] Generated {total_bytes} bytes of audio")

        except Exception as e:
            logging.error(f"[TTS STREAM] Streaming failed: {e}")
            raise Exception(f"TTS streaming failed: {str(e)}")

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
