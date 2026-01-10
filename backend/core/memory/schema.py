"""
Database schema definitions for THEO memory store.

Defines all SQLAlchemy Table objects used by the memory system.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Boolean,
    Table,
    MetaData,
    UniqueConstraint,
)


def create_schema(meta: MetaData):
    """
    Create all database table schemas.

    Args:
        meta: SQLAlchemy MetaData instance

    Returns:
        Dictionary of table name to Table object
    """

    # =============================
    # Users (Authentication)
    # =============================
    users = Table(
        "users",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("username", String, nullable=False, unique=True),
        Column("password_hash", String, nullable=False),
        Column("name", String, nullable=True),
        Column("email", String, nullable=True),
        Column("is_admin", Boolean, default=False),
        Column("is_enabled", Boolean, default=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Sessions (Authentication)
    # =============================
    auth_sessions = Table(
        "auth_sessions",
        meta,
        Column("id", String, primary_key=True),
        Column("user_id", Integer, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("expires_at", DateTime, nullable=False),
        Column("last_activity_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # API Keys (Authentication)
    # =============================
    api_keys = Table(
        "api_keys",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("key_hash", Text, nullable=False),  # bcrypt hash of the full key
        Column("name", String, nullable=True),  # user-friendly label
        Column("last_used_at", DateTime, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("expires_at", DateTime, nullable=True),  # NULL = never expires
        Column("is_revoked", Boolean, default=False),
        Column("revoked_at", DateTime, nullable=True),
    )

    # =============================
    # Mode Configuration (Work/Personal)
    # =============================
    user_mode_config = Table(
        "user_mode_config",
        meta,
        Column("user_id", Integer, nullable=False, primary_key=True),
        Column("active_mode", String, default="personal"),  # "work" or "personal"
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    mode_settings = Table(
        "mode_settings",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("mode", String, nullable=False),  # "work" or "personal"
        Column("system_prompt_override", Text, nullable=True),
        Column("preferred_provider_id", Integer, nullable=True),
        Column("tone", String, default="neutral"),  # "professional", "casual", "neutral"
        Column("pii_filtering_enabled", Boolean, default=False),  # PII redaction for work mode
        Column("pii_redaction_config", Text, nullable=True),  # JSON config for PII filtering
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Work Mode Sub-Tab Configuration
    # =============================
    work_mode_subtab_config = Table(
        "work_mode_subtab_config",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("subtab", String, nullable=False),  # "conversation", "email", "code"
        Column("config_json", Text, nullable=True),  # JSON for subtab-specific config
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Work Mode IP Restrictions
    # =============================
    work_mode_ip_config = Table(
        "work_mode_ip_config",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("enabled", Boolean, nullable=False, default=False),
        Column("allowed_ranges", Text, nullable=True),  # JSON array of CIDR ranges
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Debug Settings
    # =============================
    debug_settings = Table(
        "debug_settings",
        meta,
        Column("user_id", Integer, nullable=False, primary_key=True),  # ForeignKey("users.id") - enable in Phase 6
        Column("enabled", Boolean, default=False),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Preferences (legacy - kept for settings)
    # =============================
    preferences = Table(
        "preferences",
        meta,
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("key", String, nullable=False),
        Column("value", Text, nullable=False),
        Column("updated_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("user_id", "key", name="uq_user_preference"),
    )

    # =============================
    # System Prompt Configuration
    # =============================
    system_prompt_config = Table(
        "system_prompt_config",
        meta,
        Column("user_id", Integer, nullable=False, primary_key=True),  # ForeignKey("users.id") - enable in Phase 6
        Column("persona_name", String, default="THEO"),
        Column("tone", String, default="professional, conversational, direct"),
        Column("style_rules", Text, default="No em dashes\nBe concise first, then detailed\nProvide full working solutions when asked for code\nMaintain a consistent persona regardless of model"),
        Column("custom_instructions", Text, nullable=True),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Structured Memory
    # =============================
    memories = Table(
        "memories",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("type", String, nullable=False),  # fact, preference, goal, context
        Column("key", String, nullable=False),
        Column("value", Text, nullable=False),
        Column("relevance_score", Integer, default=100),  # 0-100, decays over time
        Column("pinned", Boolean, default=False),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("last_accessed_at", DateTime, default=datetime.utcnow),
        Column("access_count", Integer, default=0),
    )

    # =============================
    # User-Defined Intents
    # =============================
    intents = Table(
        "intents",
        meta,
        Column("id", String, primary_key=True),  # e.g., "coding", "creative"
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("name", String, nullable=False),  # Display name
        Column("description", Text, nullable=True),  # What this intent is for
        Column("keywords", Text, nullable=False),  # Comma-separated keywords
        Column("priority", Integer, default=0),  # Higher priority checked first
        Column("enabled", Boolean, default=True),
        Column("is_action", Boolean, default=False),  # True for action intents (calendar, email, etc.)
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Routing Preferences
    # =============================
    routing_preferences = Table(
        "routing_preferences",
        meta,
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("intent", String, nullable=False),
        Column("provider_id", String, nullable=False),
        Column("fallback_provider_id", String, nullable=True),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Provider Intelligence
    # =============================
    provider_metadata = Table(
        "provider_metadata",
        meta,
        Column("provider_id", String, primary_key=True),
        Column("cost_per_1k_input_tokens", Integer, default=0),  # in micro-dollars (1/1000000 of $1)
        Column("cost_per_1k_output_tokens", Integer, default=0),
        Column("avg_latency_ms", Integer, default=0),
        Column("total_requests", Integer, default=0),
        Column("failed_requests", Integer, default=0),
        Column("last_success_at", DateTime, nullable=True),
        Column("last_failure_at", DateTime, nullable=True),
        Column("health_status", String, default="unknown"),  # healthy, degraded, unhealthy, unknown
        Column("circuit_breaker_open", Boolean, default=False),
        Column("circuit_breaker_opened_at", DateTime, nullable=True),  # when circuit breaker was opened
        Column("circuit_breaker_cooldown_minutes", Integer, default=60),  # cooldown period in minutes
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    request_logs = Table(
        "request_logs",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("session_id", String, nullable=False),
        Column("provider_id", String, nullable=False),
        Column("intent", String, nullable=False),
        Column("success", Boolean, default=True),
        Column("latency_ms", Integer, nullable=True),
        Column("input_tokens", Integer, default=0),
        Column("output_tokens", Integer, default=0),
        Column("estimated_cost", Integer, default=0),  # in micro-dollars
        Column("error_message", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Voice Services Usage
    # =============================
    voice_usage_logs = Table(
        "voice_usage_logs",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("service_type", String, nullable=False),  # "tts" or "stt"
        Column("provider", String, nullable=False),  # "openai_tts_standard", "openai_tts_hd", "openai_whisper"
        Column("model", String, nullable=True),  # e.g., "tts-1", "tts-1-hd", "whisper-1"
        Column("character_count", Integer, default=0),  # for TTS
        Column("audio_duration_seconds", Integer, default=0),  # for STT
        Column("estimated_cost", Integer, default=0),  # in micro-dollars
        Column("success", Boolean, default=True),
        Column("error_message", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Providers
    # =============================
    providers = Table(
        "providers",
        meta,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("type", String, nullable=False),
        Column("base_url", String, nullable=True),
        Column("model", String, nullable=True),
        Column("api_key", Text, nullable=True),
        Column("enabled", Boolean, default=True),
        Column("suitable_for_official", Boolean, default=False),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Session Folders
    # =============================
    session_folders = Table(
        "session_folders",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(100), nullable=False),
        Column("user_id", Integer, nullable=False),
        Column("is_system", Boolean, default=False),
        Column("sort_order", Integer, default=0),
        Column("collapsed", Boolean, default=False),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("user_id", "name", name="uq_user_folder_name"),
    )

    # =============================
    # Sessions
    # =============================
    sessions = Table(
        "sessions",
        meta,
        Column("id", String, primary_key=True),
        Column("title", String, nullable=True),
        Column("mode", String, default="personal"),  # "work" or "personal"
        Column("classification", String, default="OFFICIAL"),  # UK Government classification
        Column("user_id", Integer, nullable=True),  # For filtering sessions by user
        Column("folder_id", Integer, nullable=True),  # For folder organization
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Session summaries
    # =============================
    summaries = Table(
        "summaries",
        meta,
        Column("session_id", String, nullable=False),
        Column("content", Text, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Conversation turns
    # =============================
    turns = Table(
        "turns",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("session_id", String, nullable=False),
        Column("role", String, nullable=False),
        Column("content", Text, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow),
        # Provider metadata for assistant messages
        Column("provider_id", String, nullable=True),
        Column("model", String, nullable=True),
        Column("intent", String, nullable=True),
        Column("metadata", Text, nullable=True),  # JSON metadata for confirmations, etc.
        Column("planning_metadata", Text, nullable=True),  # JSON: weather/traffic/calendar context
        Column("full_request_context", Text, nullable=True),  # JSON: full message array sent to LLM
        # Routine tracking
        Column("routine_name", String, nullable=True),  # Name of routine executed (e.g., "good_morning")
        Column("routine_actions", Text, nullable=True),  # JSON array of actions executed
    )

    # =============================
    # Session Providers
    # =============================
    session_providers = Table(
        "session_providers",
        meta,
        Column("session_id", String, primary_key=True),
        Column("provider_id", String, nullable=False),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Service Providers
    # =============================
    service_providers = Table(
        "service_providers",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("name", String, nullable=False),
        Column("category", String, nullable=False),
        Column("provider_type", String, nullable=False),
        Column("capabilities", Text, nullable=True),
        Column("api_base_url", String, nullable=True),
        Column("auth_method", String, nullable=True),
        Column("access_token", Text, nullable=True),
        Column("refresh_token", Text, nullable=True),
        Column("token_expires_at", DateTime, nullable=True),
        Column("api_endpoint_calendar", String, nullable=True),
        Column("api_endpoint_email", String, nullable=True),
        Column("additional_metadata", Text, nullable=True),
        Column("trust_level", String, default="manual"),
        Column("booking_method", String, nullable=True),
        Column("preferred_for_category", Boolean, default=False),
        Column("is_enabled", Boolean, default=True),
        Column("last_synced_at", DateTime, nullable=True),
        Column("health_status", String, default="unknown"),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Actions
    # =============================
    actions = Table(
        "actions",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("session_id", String, nullable=False),
        Column("action_type", String, nullable=False),
        Column("category", String, nullable=False),
        Column("intent_summary", Text, nullable=False),
        Column("service_provider_id", Integer, nullable=True),
        Column("action_params", Text, nullable=True),
        Column("planned_execution_time", DateTime, nullable=True),
        Column("status", String, default="pending"),
        Column("requires_confirmation", Boolean, default=True),
        Column("initiated_at", DateTime, nullable=True),
        Column("approved_at", DateTime, nullable=True),
        Column("executed_at", DateTime, nullable=True),
        Column("completed_at", DateTime, nullable=True),
        Column("result_data", Text, nullable=True),
        Column("error_message", Text, nullable=True),
        Column("retry_count", Integer, default=0),
        Column("max_retries", Integer, default=3),
        Column("is_reversible", Boolean, default=False),
        Column("rollback_action_id", Integer, nullable=True),
        Column("enrichment_data", Text, nullable=True),  # JSON: weather/traffic/calendar enrichment
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Action Confirmations
    # =============================
    action_confirmations = Table(
        "action_confirmations",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("action_id", Integer, nullable=False, unique=True),
        Column("confirmation_message", Text, nullable=False),
        Column("user_response", String, nullable=True),
        Column("user_response_text", Text, nullable=True),
        Column("modified_params", Text, nullable=True),
        Column("presented_at", DateTime, nullable=False),
        Column("responded_at", DateTime, nullable=True),
        Column("expires_at", DateTime, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # M365 Credentials
    # =============================
    m365_credentials = Table(
        "m365_credentials",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False, unique=True),
        Column("access_token", Text, nullable=False),
        Column("refresh_token", Text, nullable=False),
        Column("token_type", String, default="Bearer"),
        Column("expires_at", DateTime, nullable=False),
        Column("scope", Text, nullable=True),
        Column("tenant_id", String, nullable=True),
        Column("user_principal_name", String, nullable=True),
        Column("is_valid", Boolean, default=True),
        Column("last_refreshed_at", DateTime, nullable=True),
        Column("last_error", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # WHOOP Credentials
    # =============================
    whoop_credentials = Table(
        "whoop_credentials",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False, unique=True),
        Column("access_token", Text, nullable=False),
        Column("refresh_token", Text, nullable=False),
        Column("token_type", String, default="Bearer"),
        Column("expires_at", DateTime, nullable=False),
        Column("whoop_user_id", String, nullable=False),
        Column("is_valid", Boolean, default=True),
        Column("last_refreshed_at", DateTime, nullable=True),
        Column("last_error", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # WHOOP Settings
    # =============================
    whoop_settings = Table(
        "whoop_settings",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False, unique=True),
        Column("sleep_notifications_enabled", Boolean, default=True),
        Column("workout_notifications_enabled", Boolean, default=True),
        Column("stress_notifications_enabled", Boolean, default=True),
        Column("stress_notification_time", String, default="14:00"),
        Column("check_frequency_minutes", Integer, default=30),
        Column("quiet_hours_enabled", Boolean, default=False),
        Column("quiet_hours_start", String, nullable=True),
        Column("quiet_hours_end", String, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # WHOOP Data Tracking
    # =============================
    whoop_data_tracking = Table(
        "whoop_data_tracking",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("data_type", String, nullable=False),
        Column("whoop_id", String, nullable=False, unique=True),
        Column("notified_at", DateTime, nullable=False),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Plex Credentials
    # =============================
    plex_credentials = Table(
        "plex_credentials",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False, unique=True),
        Column("access_token", Text, nullable=False),
        Column("plex_user_id", Text, nullable=False),
        Column("plex_username", Text, nullable=True),
        Column("server_url", Text, nullable=False),
        Column("server_name", Text, nullable=True),
        Column("server_version", Text, nullable=True),
        Column("is_valid", Boolean, default=True),
        Column("last_error", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Plex Settings
    # =============================
    plex_settings = Table(
        "plex_settings",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False, unique=True),
        Column("new_episode_notifications_enabled", Boolean, default=False),
        Column("new_season_notifications_enabled", Boolean, default=False),
        Column("new_movie_notifications_enabled", Boolean, default=False),
        Column("check_frequency_minutes", Integer, default=15),
        Column("quiet_hours_start", Text, nullable=True),
        Column("quiet_hours_end", Text, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Plex Notification Tracking
    # =============================
    plex_notification_tracking = Table(
        "plex_notification_tracking",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("plex_item_key", Text, nullable=False),
        Column("plex_item_type", Text, nullable=False),
        Column("notified_at", DateTime, default=datetime.utcnow),
        Column("created_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("user_id", "plex_item_key", name="uq_plex_tracking"),
    )

    # =============================
    # Feature Providers
    # =============================
    feature_providers = Table(
        "feature_providers",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("provider_type", String(50), nullable=False),
        Column("provider_name", String(100), nullable=False),
        Column("is_enabled", Boolean, default=True),
        Column("encrypted_config", Text, nullable=True),  # JSON with OAuth credentials (encrypted)
        Column("created_at", DateTime, default=datetime.utcnow),
        Column("updated_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Feature Provider Usage Logs
    # =============================
    feature_provider_usage_logs = Table(
        "feature_provider_usage_logs",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),  # ForeignKey("users.id") - enable in Phase 6
        Column("provider_type", String(50), nullable=False),
        Column("success", Boolean, default=True),
        Column("latency_ms", Integer, nullable=True),
        Column("error_message", String, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Calendar Events Cache
    # =============================
    calendar_events_cache = Table(
        "calendar_events_cache",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=False),
        Column("event_id", String, nullable=False),
        Column("calendar_id", String, nullable=True),
        Column("subject", String, nullable=True),
        Column("start_time", DateTime, nullable=False),
        Column("end_time", DateTime, nullable=False),
        Column("location", String, nullable=True),
        Column("description", Text, nullable=True),
        Column("attendees", Text, nullable=True),
        Column("is_all_day", Boolean, default=False),
        Column("status", String, nullable=True),
        Column("importance", String, nullable=True),
        Column("fetched_at", DateTime, nullable=False),
        Column("cache_expires_at", DateTime, nullable=True),
        Column("created_at", DateTime, default=datetime.utcnow),
    )

    # =============================
    # Classification Audit
    # =============================
    classification_audit = Table(
        "classification_audit",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("user_id", Integer, nullable=True),
        Column("session_id", String, nullable=True),
        Column("classification", String, nullable=False),
        Column("action", String, nullable=False),  # 'create', 'export', 'update', 'access'
        Column("justification", Text, nullable=True),
        Column("timestamp", DateTime, default=datetime.utcnow),
    )

    return {
        "users": users,
        "auth_sessions": auth_sessions,
        "api_keys": api_keys,
        "user_mode_config": user_mode_config,
        "mode_settings": mode_settings,
        "work_mode_subtab_config": work_mode_subtab_config,
        "work_mode_ip_config": work_mode_ip_config,
        "debug_settings": debug_settings,
        "preferences": preferences,
        "system_prompt_config": system_prompt_config,
        "memories": memories,
        "intents": intents,
        "routing_preferences": routing_preferences,
        "provider_metadata": provider_metadata,
        "request_logs": request_logs,
        "voice_usage_logs": voice_usage_logs,
        "feature_provider_usage_logs": feature_provider_usage_logs,
        "providers": providers,
        "session_folders": session_folders,
        "sessions": sessions,
        "summaries": summaries,
        "turns": turns,
        "session_providers": session_providers,
        "service_providers": service_providers,
        "actions": actions,
        "action_confirmations": action_confirmations,
        "m365_credentials": m365_credentials,
        "whoop_credentials": whoop_credentials,
        "whoop_settings": whoop_settings,
        "whoop_data_tracking": whoop_data_tracking,
        "plex_credentials": plex_credentials,
        "plex_settings": plex_settings,
        "plex_notification_tracking": plex_notification_tracking,
        "calendar_events_cache": calendar_events_cache,
        "classification_audit": classification_audit,
        "feature_providers": feature_providers,
    }
