"""
Voice API routes for Text-to-Speech and Speech-to-Text.

Endpoints:
- POST /api/voice/tts - Convert text to speech
- POST /api/voice/stt - Convert speech to text
- GET /api/voice/voices - List available TTS voices
"""

from flask import Blueprint, request, jsonify, send_file
from io import BytesIO
import logging

from voice.tts_openai import OpenAITTSProvider
from voice.stt_openai import OpenAIWhisperProvider
from core.provider_registry import ProviderRegistry
from core.memory import MemoryStore
from config import Config
from auth.password import require_auth

voice_bp = Blueprint("voice", __name__)


def get_tts_provider():
    """Get configured TTS provider."""
    try:
        from app import provider_registry

        # Get OpenAI provider config
        openai_config = provider_registry.get_by_type("openai")

        if not openai_config or not openai_config.get("api_key"):
            return None, "OpenAI API key not configured"

        # Use standard tts-1 model
        provider = OpenAITTSProvider(
            api_key=openai_config["api_key"],
            model="tts-1"
        )

        return provider, None

    except Exception as e:
        logging.error(f"[VOICE_ROUTES] Failed to initialize TTS provider: {e}")
        return None, str(e)


def get_stt_provider():
    """Get configured STT provider."""
    try:
        from app import provider_registry

        # Get OpenAI provider config
        openai_config = provider_registry.get_by_type("openai")

        if not openai_config or not openai_config.get("api_key"):
            return None, "OpenAI API key not configured"

        provider = OpenAIWhisperProvider(
            api_key=openai_config["api_key"]
        )

        return provider, None

    except Exception as e:
        logging.error(f"[VOICE_ROUTES] Failed to initialize STT provider: {e}")
        return None, str(e)


@voice_bp.route("/tts", methods=["POST"])
@require_auth(lambda: MemoryStore(Config.DATABASE_URL))
def text_to_speech():
    """
    Convert text to speech audio.

    Request body:
        {
            "text": "Text to convert to speech",
            "voice": "alloy" (optional),
            "speed": 1.0 (optional, 0.25-4.0)
        }

    Returns:
        Audio file (MP3)
    """
    try:
        data = request.get_json()

        if not data or "text" not in data:
            return jsonify({"error": "Missing 'text' parameter"}), 400

        text = data["text"]
        voice = data.get("voice", "alloy")
        speed = float(data.get("speed", 1.0))

        # Get TTS provider
        provider, error = get_tts_provider()
        if error:
            return jsonify({"error": error}), 500

        # Synthesize speech
        audio_bytes = provider.synthesize(
            text=text,
            voice=voice,
            speed=speed,
            output_format="mp3"
        )

        # Calculate cost and log usage
        character_count = len(text)
        model = provider.model  # tts-1 or tts-1-hd

        # OpenAI TTS pricing (in micro-dollars per 1K characters)
        # tts-1: $15/1M chars = $0.015/1K chars = 15,000 micro-dollars/1K chars
        # tts-1-hd: $30/1M chars = $0.030/1K chars = 30,000 micro-dollars/1K chars
        cost_per_1k_chars = 30000 if model == "tts-1-hd" else 15000
        estimated_cost = int((character_count / 1000) * cost_per_1k_chars)

        # Log usage
        memory = MemoryStore(Config.DATABASE_URL)
        memory.log_tts_usage(
            model=model,
            character_count=character_count,
            estimated_cost=estimated_cost,
            success=True
        )

        # Return audio file
        return send_file(
            BytesIO(audio_bytes),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="speech.mp3"
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"[VOICE_ROUTES] TTS error: {e}")

        # Log failed request
        try:
            if 'text' in locals():
                memory = MemoryStore(Config.DATABASE_URL)
                memory.log_tts_usage(
                    model="tts-1-hd",
                    character_count=len(text),
                    estimated_cost=0,
                    success=False,
                    error_message=str(e)
                )
        except:
            pass

        return jsonify({"error": str(e)}), 500


@voice_bp.route("/tts/stream", methods=["POST"])
@require_auth(lambda: MemoryStore(Config.DATABASE_URL))
def text_to_speech_stream():
    """
    Convert text to speech with streaming audio.
    Enables progressive playback starting within 2-3 seconds.

    Request body:
        {
            "text": "Text to convert to speech",
            "voice": "alloy" (optional),
            "speed": 1.0 (optional, 0.25-4.0)
        }

    Returns:
        Streaming audio chunks (audio/mpeg)
    """
    try:
        data = request.get_json()

        if not data or "text" not in data:
            return jsonify({"error": "Missing 'text' parameter"}), 400

        text = data["text"]
        voice = data.get("voice", "alloy")
        speed = float(data.get("speed", 1.0))

        # Get TTS provider
        provider, error = get_tts_provider()
        if error:
            return jsonify({"error": error}), 500

        # Calculate cost for logging
        character_count = len(text)
        model = provider.model  # tts-1
        cost_per_1k_chars = 15000  # $15/1M chars = 15,000 micro-dollars/1K
        estimated_cost = int((character_count / 1000) * cost_per_1k_chars)

        def generate_audio():
            """Generator function for streaming audio chunks."""
            try:
                total_bytes = 0
                chunk_count = 0

                logging.info(f"[TTS STREAM] Starting stream for {character_count} characters")

                # Stream audio chunks from provider
                for audio_chunk in provider.synthesize_stream(
                    text=text,
                    voice=voice,
                    speed=speed,
                    output_format="mp3"
                ):
                    total_bytes += len(audio_chunk)
                    chunk_count += 1

                    if chunk_count == 1:
                        logging.info(f"[TTS STREAM] First chunk sent ({len(audio_chunk)} bytes)")

                    yield audio_chunk

                logging.info(f"[TTS STREAM] Complete: {chunk_count} chunks, {total_bytes} bytes")

                # Log successful usage after stream completes
                memory = MemoryStore(Config.DATABASE_URL)
                memory.log_tts_usage(
                    model=model,
                    character_count=character_count,
                    estimated_cost=estimated_cost,
                    success=True
                )

            except Exception as e:
                logging.error(f"[TTS STREAM] Error during streaming: {e}")

                # Log failed usage
                try:
                    memory = MemoryStore(Config.DATABASE_URL)
                    memory.log_tts_usage(
                        model=model,
                        character_count=character_count,
                        estimated_cost=0,
                        success=False,
                        error_message=str(e)
                    )
                except:
                    pass

                raise

        # Return streaming response with proper headers
        from flask import Response, stream_with_context

        return Response(
            stream_with_context(generate_audio()),
            mimetype="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Transfer-Encoding": "chunked"
            }
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"[TTS STREAM] Route error: {e}")
        return jsonify({"error": str(e)}), 500


@voice_bp.route("/stt", methods=["POST"])
@require_auth(lambda: MemoryStore(Config.DATABASE_URL))
def speech_to_text():
    """
    Convert speech audio to text.

    Request:
        Form data with audio file
        - audio: Audio file (webm, mp3, wav, m4a, etc.)
        - language: Optional language code (e.g., 'en', 'es')

    Returns:
        {
            "text": "Transcribed text",
            "language": "en"
        }
    """
    try:
        # Check if audio file is present
        if "audio" not in request.files:
            return jsonify({"error": "Missing 'audio' file"}), 400

        audio_file = request.files["audio"]

        if audio_file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Read audio data
        audio_data = audio_file.read()

        # Get audio format from filename or default to webm
        audio_format = request.form.get("format", "webm")
        if audio_file.filename:
            ext = audio_file.filename.rsplit(".", 1)[-1].lower()
            if ext in ["webm", "mp3", "wav", "m4a", "mp4", "mpeg", "mpga", "ogg", "flac"]:
                audio_format = ext

        # Optional language parameter
        language = request.form.get("language", None)

        # Get STT provider
        provider, error = get_stt_provider()
        if error:
            return jsonify({"error": error}), 500

        # Transcribe
        result = provider.transcribe(
            audio_data=audio_data,
            audio_format=audio_format,
            language=language
        )

        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"[VOICE_ROUTES] STT error: {e}")
        return jsonify({"error": str(e)}), 500


@voice_bp.route("/voices", methods=["GET"])
@require_auth(lambda: MemoryStore(Config.DATABASE_URL))
def list_voices():
    """
    List available TTS voices.

    Returns:
        {
            "voices": [
                {
                    "id": "alloy",
                    "name": "Alloy",
                    "description": "Neutral, balanced voice"
                },
                ...
            ]
        }
    """
    try:
        provider, error = get_tts_provider()
        if error:
            return jsonify({"error": error}), 500

        voices = provider.list_voices()

        return jsonify({"voices": voices})

    except Exception as e:
        logging.error(f"[VOICE_ROUTES] List voices error: {e}")
        return jsonify({"error": str(e)}), 500
