"""
Voice service operations for tracking TTS and STT usage and costs.
"""

from datetime import datetime, timedelta
from sqlalchemy import select, insert, func


class VoiceOperations:
    """Operations for voice service usage tracking and cost calculation."""

    def __init__(self, engine, tables):
        """
        Initialize VoiceOperations.

        Args:
            engine: SQLAlchemy engine
            tables: Dictionary of table objects from schema
        """
        self.engine = engine
        self.voice_usage_logs = tables["voice_usage_logs"]

    def _get_connection(self):
        """Get database connection."""
        return self.engine.connect()

    def log_tts_usage(self, model, character_count, estimated_cost, success=True, error_message=None):
        """
        Log a TTS (text-to-speech) request.

        Args:
            model: TTS model used (e.g., "tts-1", "tts-1-hd")
            character_count: Number of characters synthesized
            estimated_cost: Cost in micro-dollars
            success: Whether the request succeeded
            error_message: Error message if failed
        """
        provider = "openai_tts_hd" if model == "tts-1-hd" else "openai_tts_standard"

        with self._get_connection() as conn:
            conn.execute(
                insert(self.voice_usage_logs).values(
                    service_type="tts",
                    provider=provider,
                    model=model,
                    character_count=character_count,
                    audio_duration_seconds=0,
                    estimated_cost=estimated_cost,
                    success=success,
                    error_message=error_message,
                    created_at=datetime.utcnow(),
                )
            )
            conn.commit()

    def log_stt_usage(self, model, audio_duration_seconds, estimated_cost, success=True, error_message=None):
        """
        Log an STT (speech-to-text) request.

        Args:
            model: STT model used (e.g., "whisper-1")
            audio_duration_seconds: Duration of audio in seconds
            estimated_cost: Cost in micro-dollars
            success: Whether the request succeeded
            error_message: Error message if failed
        """
        with self._get_connection() as conn:
            conn.execute(
                insert(self.voice_usage_logs).values(
                    service_type="stt",
                    provider="openai_whisper",
                    model=model,
                    character_count=0,
                    audio_duration_seconds=audio_duration_seconds,
                    estimated_cost=estimated_cost,
                    success=success,
                    error_message=error_message,
                    created_at=datetime.utcnow(),
                )
            )
            conn.commit()

    def get_voice_costs(self, days=30):
        """
        Calculate voice service costs for the specified period.

        Args:
            days: Number of days to look back (7, 30, 90, or None for all-time)

        Returns:
            Dictionary with voice service costs
        """
        with self._get_connection() as conn:
            # Build query with optional date filter
            query = select(
                self.voice_usage_logs.c.service_type,
                self.voice_usage_logs.c.provider,
                func.sum(self.voice_usage_logs.c.character_count).label("total_characters"),
                func.sum(self.voice_usage_logs.c.audio_duration_seconds).label("total_audio_seconds"),
                func.sum(self.voice_usage_logs.c.estimated_cost).label("total_cost_microdollars"),
                func.count(self.voice_usage_logs.c.id).label("request_count")
            ).group_by(
                self.voice_usage_logs.c.service_type,
                self.voice_usage_logs.c.provider
            )

            # Apply date filter if specified
            if days is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = query.where(self.voice_usage_logs.c.created_at >= cutoff_date)

            rows = conn.execute(query).fetchall()

            # Build response
            services = []
            total_cost_usd = 0.0
            total_requests = 0

            for row in rows:
                cost_usd = row.total_cost_microdollars / 1_000_000 if row.total_cost_microdollars else 0.0
                total_cost_usd += cost_usd
                total_requests += row.request_count or 0

                # Friendly service names
                service_name_map = {
                    ("tts", "openai_tts_standard"): "OpenAI TTS (Standard)",
                    ("tts", "openai_tts_hd"): "OpenAI TTS (HD)",
                    ("stt", "openai_whisper"): "OpenAI Whisper (STT)",
                }
                service_name = service_name_map.get((row.service_type, row.provider), f"{row.provider} ({row.service_type.upper()})")

                services.append({
                    "service_type": row.service_type,
                    "provider": row.provider,
                    "name": service_name,
                    "total_cost_usd": round(cost_usd, 6),
                    "total_characters": row.total_characters or 0,
                    "total_audio_seconds": row.total_audio_seconds or 0,
                    "request_count": row.request_count or 0
                })

            return {
                "services": services,
                "total_cost_usd": round(total_cost_usd, 6),
                "total_requests": total_requests,
                "period_days": days
            }
