"""
Main MemoryStore class.

Delegates to specialized operation modules using a clean modular architecture.
All table definitions are centralized in schema.py.
"""

from datetime import datetime
from sqlalchemy import create_engine, MetaData, select, insert, update, delete
from sqlalchemy.orm import sessionmaker

from .schema import create_schema
from .memories import MemoryOperations
from .intents import IntentOperations
from .sessions import SessionOperations
from .folders import FolderOperations
from .providers import ProviderOperations
from .users import UserOperations
from .modes import ModeOperations
from .work_mode_ip import WorkModeIPOperations
from .service_providers import ServiceProviderOperations
from .m365 import M365Operations
from .whoop import WHOOPOperations
from .plex import PlexOperations
from .actions import ActionOperations
from .voice import VoiceOperations
from .routines import RoutineOperations


class MemoryStore:
    """
    Modular MemoryStore - Clean architecture with centralized schema.

    Delegates operations to specialized modules:
    - memories.py: Memory and preference operations
    - intents.py: Intent and routing operations
    - sessions.py: Session and conversation management
    - providers.py: AI provider management
    - users.py: User and authentication operations
    - modes.py: Work/Personal mode configuration
    - service_providers.py: External service provider integration
    - m365.py: Microsoft 365 integration
    - actions.py: Action and confirmation system
    """

    def __init__(self, db_url):
        """
        Initialize memory store.

        Args:
            db_url: SQLAlchemy database URL
        """
        # Create engine and metadata
        # For SQLite: Use URI mode to handle file paths properly and set timeout
        if db_url.startswith("sqlite"):
            # Add connect_args for SQLite to handle concurrent access better
            self.engine = create_engine(
                db_url,
                connect_args={
                    "timeout": 30,  # Wait up to 30 seconds for locks
                    "check_same_thread": False  # Allow multi-threading
                },
                pool_pre_ping=True  # Verify connections before using
            )
        else:
            self.engine = create_engine(db_url)
        self.meta = MetaData()

        # Create all table definitions from centralized schema
        tables = create_schema(self.meta)

        # Assign tables as instance attributes for compatibility
        self.users = tables["users"]
        self.auth_sessions = tables["auth_sessions"]
        self.api_keys = tables["api_keys"]
        self.user_mode_config = tables["user_mode_config"]
        self.mode_settings = tables["mode_settings"]
        self.work_mode_subtab_config = tables["work_mode_subtab_config"]
        self.work_mode_ip_config = tables["work_mode_ip_config"]
        self.debug_settings = tables["debug_settings"]
        self.preferences = tables["preferences"]
        self.system_prompt_config = tables["system_prompt_config"]
        self.memories = tables["memories"]
        self.intents = tables["intents"]
        self.routing_preferences = tables["routing_preferences"]
        self.provider_metadata = tables["provider_metadata"]
        self.request_logs = tables["request_logs"]
        self.providers = tables["providers"]
        self.sessions = tables["sessions"]
        self.summaries = tables["summaries"]
        self.turns = tables["turns"]
        self.session_providers = tables["session_providers"]
        self.service_providers = tables["service_providers"]
        self.actions = tables["actions"]
        self.action_confirmations = tables["action_confirmations"]
        self.m365_credentials = tables["m365_credentials"]
        self.calendar_events_cache = tables["calendar_events_cache"]
        self.classification_audit = tables["classification_audit"]

        # Store tables dict for easy access
        self.tables = tables

        # Create all tables
        self.meta.create_all(self.engine)

        # Create session maker
        self.Session = sessionmaker(bind=self.engine)

        # Initialize specialized operation modules
        self._memory_ops = MemoryOperations(tables, self.Session, self.engine)
        self._intent_ops = IntentOperations(tables, self.Session, self.engine)
        self._session_ops = SessionOperations(tables, self.Session, self.engine)
        self._folder_ops = FolderOperations(tables, self.Session, self.engine)
        self._provider_ops = ProviderOperations(tables, self.Session, self.engine)
        self._user_ops = UserOperations(tables, self.Session, self.engine)
        self._mode_ops = ModeOperations(tables, self.Session, self.engine)
        self._work_mode_ip_ops = WorkModeIPOperations(tables, self.Session, self.engine)
        self._service_provider_ops = ServiceProviderOperations(tables, self.Session, self.engine)
        self._m365_ops = M365Operations(tables, self.Session, self.engine)
        self._whoop_ops = WHOOPOperations(tables, self.Session, self.engine)
        self._plex_ops = PlexOperations(tables, self.Session, self.engine)
        self._action_ops = ActionOperations(tables, self.Session, self.engine)
        self._routine_ops = RoutineOperations(self.engine)
        self._voice_ops = VoiceOperations(self.engine, tables)

    # =============================
    # Memory Operations (delegated)
    # =============================

    def remember(self, user_id, key, value):
        """Store a user preference."""
        return self._memory_ops.remember(user_id, key, value)

    def forget(self, user_id, key):
        """Remove a user preference."""
        return self._memory_ops.forget(user_id, key)

    def get_all(self, user_id):
        """Get all user preferences."""
        return self._memory_ops.get_all(user_id)

    def store_memory(self, user_id, memory_type, key, value, pinned=False):
        """Store a structured memory."""
        return self._memory_ops.store_memory(user_id, memory_type, key, value, pinned)

    def get_memories(self, user_id, memory_type=None, limit=None):
        """Retrieve memories, optionally filtered by type."""
        return self._memory_ops.get_memories(user_id, memory_type, limit)

    def get_relevant_memories(self, user_id, query_text, max_results=7):
        """Score and return most relevant memories for a given query."""
        return self._memory_ops.get_relevant_memories(user_id, query_text, max_results)

    def delete_memory(self, user_id, memory_id):
        """Permanently delete a memory by ID."""
        return self._memory_ops.delete_memory(user_id, memory_id)

    def update_memory(self, user_id, memory_id, memory_type=None, key=None, value=None):
        """Update an existing memory by ID."""
        return self._memory_ops.update_memory(user_id, memory_id, memory_type, key, value)

    def pin_memory(self, user_id, memory_id, pinned=True):
        """Pin or unpin a memory."""
        return self._memory_ops.pin_memory(user_id, memory_id, pinned)

    def decay_memory_scores(self, user_id, decay_amount=1):
        """Apply time-based decay to all non-pinned memories."""
        return self._memory_ops.decay_memory_scores(user_id, decay_amount)

    def get_system_prompt_config(self, user_id):
        """Get system prompt configuration for a user."""
        return self._memory_ops.get_system_prompt_config(user_id)

    def update_system_prompt_config(self, user_id, **updates):
        """Update system prompt configuration."""
        return self._memory_ops.update_system_prompt_config(user_id, **updates)

    # =============================
    # Intent Operations (delegated)
    # =============================

    def set_routing_preference(self, user_id, intent, provider_id, fallback_provider_id=None):
        """Set routing preference for an intent."""
        return self._intent_ops.set_routing_preference(user_id, intent, provider_id, fallback_provider_id)

    def get_routing_preferences(self, user_id):
        """Get all routing preferences for a user."""
        return self._intent_ops.get_routing_preferences(user_id)

    def delete_routing_preference(self, user_id, intent):
        """Delete a routing preference."""
        return self._intent_ops.delete_routing_preference(user_id, intent)

    def get_routing_provider(self, user_id, intent):
        """Get provider ID for a specific intent."""
        return self._intent_ops.get_routing_provider(user_id, intent)

    def get_fallback_provider(self, user_id, intent):
        """Get fallback provider ID for a specific intent."""
        return self._intent_ops.get_fallback_provider(user_id, intent)

    def set_routing_provider(self, user_id, intent, provider_id):
        """Alias for set_routing_preference."""
        return self._intent_ops.set_routing_provider(user_id, intent, provider_id)

    def list_intents(self, user_id):
        """Get all intents for a user."""
        return self._intent_ops.list_intents(user_id)

    def get_intent(self, user_id, intent_id):
        """Get a single intent by ID."""
        return self._intent_ops.get_intent(user_id, intent_id)

    def create_intent(self, user_id, intent_id, name, description, keywords, priority=0, enabled=True):
        """Create a new intent."""
        return self._intent_ops.create_intent(user_id, intent_id, name, description, keywords, priority, enabled)

    def update_intent(self, user_id, intent_id, **updates):
        """Update an existing intent."""
        return self._intent_ops.update_intent(user_id, intent_id, **updates)

    def delete_intent(self, user_id, intent_id):
        """Delete an intent and its routing preferences."""
        return self._intent_ops.delete_intent(user_id, intent_id)

    def seed_default_intents(self, user_id):
        """Seed default intents if none exist for the user."""
        return self._intent_ops.seed_default_intents(user_id)

    def get_action_intents(self, user_id):
        """Get all enabled action intents for a user."""
        return self._intent_ops.get_action_intents(user_id)

    # =============================
    # Session Operations (delegated)
    # =============================

    def _ensure_session(self, session_id):
        """Ensure a session exists in the database."""
        return self._session_ops._ensure_session(session_id)

    def save_session_title(self, session_id, title):
        """Save or update a session title."""
        return self._session_ops.save_session_title(session_id, title)

    def list_sessions(self, user_id=None, mode=None):
        """Return all sessions with their latest summary."""
        return self._session_ops.list_sessions(user_id=user_id, mode=mode)

    def delete_session(self, session_id):
        """Permanently delete a session and all associated data."""
        return self._session_ops.delete_session(session_id)

    def save_session_summary(self, session_id, content):
        """Save a conversation summary for a session."""
        return self._session_ops.save_session_summary(session_id, content)

    def get_session_summary(self, session_id):
        """Get the latest summary for a session."""
        return self._session_ops.get_session_summary(session_id)

    def should_generate_summary(self, session_id, threshold=20):
        """Check if a summary should be generated for this session."""
        return self._session_ops.should_generate_summary(session_id, threshold)

    def generate_auto_summary(self, session_id, provider_call):
        """Generate an automatic summary of the conversation using an LLM."""
        return self._session_ops.generate_auto_summary(session_id, provider_call)

    def save_turn(self, session_id, role, content, created_at=None, provider_id=None, model=None, intent=None, metadata=None, mode="personal", user_id=None, routine_name=None, routine_actions=None, full_request_context=None):
        """Save a conversation turn (message)."""
        return self._session_ops.save_turn(session_id, role, content, created_at, provider_id, model, intent, metadata, mode, user_id, routine_name, routine_actions, full_request_context)

    def get_recent_turns(self, session_id, limit=6):
        """Get recent conversation turns for a session."""
        return self._session_ops.get_recent_turns(session_id, limit)

    def build_context(self, session_id, system_prompt, limit=12):
        """Build deterministic context for model invocation."""
        return self._session_ops.build_context(session_id, system_prompt, limit)

    def update_turn_metadata(self, session_id, role, metadata):
        """Update metadata for the most recent turn matching session_id and role."""
        return self._session_ops.update_turn_metadata(session_id, role, metadata)

    def delete_turn(self, turn_id):
        """Delete a specific turn by ID."""
        return self._session_ops.delete_turn(turn_id)

    # =============================
    # Folder Operations (delegated)
    # =============================

    def create_folder(self, user_id, name):
        """Create a new folder for organizing sessions."""
        return self._folder_ops.create_folder(user_id, name)

    def get_folders(self, user_id):
        """Get all folders for a user (Archive always first)."""
        return self._folder_ops.get_folders(user_id)

    def get_folder_by_id(self, folder_id, user_id):
        """Get a specific folder by ID."""
        return self._folder_ops.get_folder_by_id(folder_id, user_id)

    def rename_folder(self, folder_id, user_id, new_name):
        """Rename a folder (system folders protected)."""
        return self._folder_ops.rename_folder(folder_id, user_id, new_name)

    def delete_folder(self, folder_id, user_id):
        """Delete a folder (sessions become unfiled)."""
        return self._folder_ops.delete_folder(folder_id, user_id)

    def update_folder_collapsed(self, folder_id, user_id, collapsed):
        """Toggle folder expand/collapse state."""
        return self._folder_ops.update_folder_collapsed(folder_id, user_id, collapsed)

    def reorder_folders(self, user_id, folder_order):
        """Update sort order for multiple folders."""
        return self._folder_ops.reorder_folders(user_id, folder_order)

    def move_session_to_folder(self, session_id, folder_id, user_id):
        """Move session to folder (or unfiled if folder_id=None)."""
        return self._folder_ops.move_session_to_folder(session_id, folder_id, user_id)

    def archive_session(self, session_id, user_id):
        """Move session to Archive folder."""
        return self._folder_ops.archive_session(session_id, user_id)

    def get_archive_folder_id(self, user_id):
        """Get the Archive folder ID for a user."""
        return self._folder_ops.get_archive_folder_id(user_id)

    # =============================
    # Provider Operations (delegated)
    # =============================

    def list_providers(self):
        """Get all providers."""
        return self._provider_ops.list_providers()

    def get_provider(self, provider_id):
        """Get a specific provider by ID."""
        return self._provider_ops.get_provider(provider_id)

    def upsert_provider(self, provider):
        """Insert or update a provider."""
        return self._provider_ops.upsert_provider(provider)

    def delete_provider(self, provider_id):
        """Delete a provider."""
        return self._provider_ops.delete_provider(provider_id)

    def init_provider_metadata(self, provider_id, cost_per_1k_input=0, cost_per_1k_output=0):
        """Initialize provider metadata with cost data."""
        return self._provider_ops.init_provider_metadata(provider_id, cost_per_1k_input, cost_per_1k_output)

    def get_provider_metadata(self, provider_id):
        """Get metadata for a specific provider."""
        return self._provider_ops.get_provider_metadata(provider_id)

    def get_all_provider_metadata(self):
        """Get metadata for all providers."""
        return self._provider_ops.get_all_provider_metadata()

    def log_request(self, session_id, provider_id, intent, success, latency_ms,
                   input_tokens=0, output_tokens=0, estimated_cost=0, error_message=None):
        """Log a provider request for analytics and health tracking."""
        return self._provider_ops.log_request(
            session_id, provider_id, intent, success, latency_ms,
            input_tokens, output_tokens, estimated_cost, error_message
        )

    def update_provider_health(self, provider_id, success, latency_ms=None):
        """Update provider health metrics based on request outcome."""
        return self._provider_ops.update_provider_health(provider_id, success, latency_ms)

    def get_provider_health_summary(self):
        """Get health summary for all providers."""
        return self._provider_ops.get_provider_health_summary()

    def reset_provider_health(self, provider_id):
        """Reset health metrics for a provider."""
        return self._provider_ops.reset_provider_health(provider_id)

    def update_circuit_breaker_cooldown(self, provider_id, cooldown_minutes):
        """Update circuit breaker cooldown period for a provider."""
        return self._provider_ops.update_circuit_breaker_cooldown(provider_id, cooldown_minutes)

    def reset_all_provider_usage(self):
        """Reset ALL provider usage data (destructive operation)."""
        return self._provider_ops.reset_all_provider_usage()

    def get_provider_costs(self, days=30):
        """Get provider costs for specified period."""
        return self._provider_ops.get_provider_costs(days)

    def estimate_cost(self, provider_id, input_tokens, output_tokens):
        """Estimate cost for a request in micro-dollars."""
        return self._provider_ops.estimate_cost(provider_id, input_tokens, output_tokens)

    def delete_provider_metadata(self, provider_id):
        """Delete provider metadata and request logs when provider is removed."""
        return self._provider_ops.delete_provider_metadata(provider_id)

    def set_last_provider(self, session_id, provider_id):
        """Set the last provider used for a session."""
        return self._provider_ops.set_last_provider(session_id, provider_id)

    def get_last_provider(self, session_id):
        """Get the last provider used for a session."""
        return self._provider_ops.get_last_provider(session_id)

    # =============================
    # User Operations (delegated)
    # =============================

    def create_user(self, username, password_hash, is_admin=False, name=None, email=None):
        """Create a new user."""
        return self._user_ops.create_user(username, password_hash, is_admin, name, email)

    def get_user_by_username(self, username):
        """Get user by username."""
        return self._user_ops.get_user_by_username(username)

    def get_user_by_id(self, user_id):
        """Get user by ID."""
        return self._user_ops.get_user_by_id(user_id)

    def update_user_password(self, user_id, password_hash):
        """Update user password."""
        return self._user_ops.update_user_password(user_id, password_hash)

    def disable_user(self, user_id):
        """Disable a user account."""
        return self._user_ops.disable_user(user_id)

    def list_all_users(self, include_disabled=False):
        """List all users."""
        return self._user_ops.list_all_users(include_disabled)

    def update_user(self, user_id, updates):
        """Update user fields."""
        return self._user_ops.update_user(user_id, updates)

    def enable_user(self, user_id):
        """Enable disabled user account."""
        return self._user_ops.enable_user(user_id)

    def reset_user_password(self, user_id, new_password_hash):
        """Admin reset user password and invalidate sessions."""
        return self._user_ops.reset_user_password(user_id, new_password_hash)

    def get_user_activity_stats(self, user_id):
        """Get user activity metrics."""
        return self._user_ops.get_user_activity_stats(user_id)

    def count_admins(self):
        """Count total enabled admin users."""
        return self._user_ops.count_admins()

    def create_auth_session(self, session_id, user_id, expires_at):
        """Create an authentication session."""
        return self._user_ops.create_auth_session(session_id, user_id, expires_at)

    def get_auth_session(self, session_id):
        """Get authentication session."""
        return self._user_ops.get_auth_session(session_id)

    def delete_auth_session(self, session_id):
        """Delete authentication session (logout)."""
        return self._user_ops.delete_auth_session(session_id)

    def update_session_activity(self, session_id):
        """Update last activity timestamp for a session."""
        return self._user_ops.update_session_activity(session_id)

    def cleanup_expired_sessions(self):
        """Remove expired authentication sessions."""
        return self._user_ops.cleanup_expired_sessions()

    def set_debug_enabled(self, user_id, enabled: bool):
        """Set debug enabled flag for a user."""
        return self._user_ops.set_debug_enabled(user_id, enabled)

    def is_debug_enabled(self, user_id) -> bool:
        """Check if debug logging is enabled for a user."""
        return self._user_ops.is_debug_enabled(user_id)

    # =============================
    # API Key Management
    # =============================

    def create_api_key(self, user_id, name, key_hash, expires_at=None):
        """Create a new API key for a user."""
        return self._user_ops.create_api_key(user_id, name, key_hash, expires_at)

    def get_api_key_by_id(self, key_id, user_id=None):
        """Get API key by ID."""
        return self._user_ops.get_api_key_by_id(key_id, user_id)

    def find_api_key_by_hash(self, key_hash):
        """Find API key by its hash (for authentication)."""
        return self._user_ops.find_api_key_by_hash(key_hash)

    def list_user_api_keys(self, user_id):
        """List all API keys for a user."""
        return self._user_ops.list_user_api_keys(user_id)

    def update_api_key_last_used(self, key_id):
        """Update the last used timestamp for an API key."""
        return self._user_ops.update_api_key_last_used(key_id)

    def revoke_api_key(self, key_id, user_id):
        """Revoke an API key (soft delete)."""
        return self._user_ops.revoke_api_key(key_id, user_id)

    def delete_api_key(self, key_id, user_id):
        """Permanently delete an API key."""
        return self._user_ops.delete_api_key(key_id, user_id)

    def update_api_key_name(self, key_id, user_id, new_name):
        """Update the name of an API key."""
        return self._user_ops.update_api_key_name(key_id, user_id, new_name)

    # =============================
    # Mode Operations (delegated)
    # =============================

    def get_user_mode(self, user_id):
        """Get user's active mode."""
        return self._mode_ops.get_user_mode(user_id)

    def set_user_mode(self, user_id, mode):
        """Set user's active mode."""
        return self._mode_ops.set_user_mode(user_id, mode)

    def get_mode_settings(self, user_id, mode):
        """Get settings for a specific mode."""
        return self._mode_ops.get_mode_settings(user_id, mode)

    def create_or_update_mode_settings(self, user_id, mode, system_prompt_override=None,
                                       preferred_provider_id=None, tone=None,
                                       pii_filtering_enabled=None, pii_redaction_config=None):
        """Create or update mode settings."""
        return self._mode_ops.create_or_update_mode_settings(
            user_id, mode, system_prompt_override, preferred_provider_id, tone,
            pii_filtering_enabled, pii_redaction_config
        )

    def get_all_mode_settings(self, user_id):
        """Get all mode settings for a user."""
        return self._mode_ops.get_all_mode_settings(user_id)

    def get_work_subtab_config(self, user_id, subtab):
        """Get configuration for a specific work subtab."""
        return self._mode_ops.get_work_subtab_config(user_id, subtab)

    def update_work_subtab_config(self, user_id, subtab, config_json):
        """Update configuration for a specific work subtab."""
        return self._mode_ops.update_work_subtab_config(user_id, subtab, config_json)

    def get_all_work_subtab_configs(self, user_id):
        """Get all work subtab configurations for a user."""
        return self._mode_ops.get_all_work_subtab_configs(user_id)

    # =============================
    # Work Mode IP Operations (delegated)
    # =============================

    def get_work_mode_ip_config(self):
        """Get Work Mode IP restriction configuration."""
        return self._work_mode_ip_ops.get_ip_config()

    def update_work_mode_ip_config(self, enabled, allowed_ranges):
        """Update Work Mode IP restriction configuration."""
        return self._work_mode_ip_ops.update_ip_config(enabled, allowed_ranges)

    def is_ip_allowed_for_work_mode(self, ip_address):
        """Check if an IP address is allowed for Work Mode access."""
        return self._work_mode_ip_ops.is_ip_allowed(ip_address)

    # =============================
    # Service Provider Operations (delegated)
    # =============================

    def store_service_provider(self, user_id, name, category, provider_type, **kwargs):
        """Store a new service provider."""
        return self._service_provider_ops.store_service_provider(
            user_id, name, category, provider_type, **kwargs
        )

    def get_service_providers(self, user_id, category=None):
        """Get service providers for a user."""
        return self._service_provider_ops.get_service_providers(user_id, category)

    def get_service_provider(self, provider_id):
        """Get a single service provider by ID."""
        return self._service_provider_ops.get_service_provider(provider_id)

    def get_service_providers_by_type(self, user_id, provider_type):
        """Get service providers by type."""
        return self._service_provider_ops.get_service_providers_by_type(user_id, provider_type)

    def get_preferred_provider(self, user_id, category):
        """Get the preferred provider for a category."""
        return self._service_provider_ops.get_preferred_provider(user_id, category)

    def update_service_provider(self, provider_id, **kwargs):
        """Update a service provider."""
        return self._service_provider_ops.update_service_provider(provider_id, **kwargs)

    def delete_service_provider(self, provider_id, user_id):
        """Delete a service provider."""
        return self._service_provider_ops.delete_service_provider(provider_id, user_id)

    # =============================
    # M365 Operations (delegated)
    # =============================

    def store_m365_credentials(self, user_id, access_token, refresh_token,
                                expires_at, scope=None, tenant_id=None, upn=None):
        """Store M365 OAuth credentials."""
        return self._m365_ops.store_m365_credentials(
            user_id, access_token, refresh_token, expires_at, scope, tenant_id, upn
        )

    def get_m365_credentials(self, user_id):
        """Get M365 credentials for a user."""
        return self._m365_ops.get_m365_credentials(user_id)

    def invalidate_m365_credentials(self, user_id, error=None):
        """Mark M365 credentials as invalid."""
        return self._m365_ops.invalidate_m365_credentials(user_id, error)

    def delete_m365_credentials(self, user_id):
        """Delete M365 credentials for a user."""
        return self._m365_ops.delete_m365_credentials(user_id)

    # =============================
    # WHOOP Operations (delegated)
    # =============================

    def store_whoop_credentials(self, user_id, access_token, refresh_token,
                                 expires_at, whoop_user_id, token_type="Bearer"):
        """Store WHOOP OAuth credentials."""
        return self._whoop_ops.store_whoop_credentials(
            user_id, access_token, refresh_token, expires_at, whoop_user_id, token_type
        )

    def get_whoop_credentials(self, user_id):
        """Get WHOOP credentials for a user."""
        return self._whoop_ops.get_whoop_credentials(user_id)

    def update_whoop_token(self, user_id, access_token, expires_at, refresh_token=None):
        """Update WHOOP access token after refresh."""
        return self._whoop_ops.update_whoop_token(user_id, access_token, expires_at, refresh_token)

    def invalidate_whoop_credentials(self, user_id, error=None):
        """Mark WHOOP credentials as invalid."""
        return self._whoop_ops.invalidate_whoop_credentials(user_id, error)

    def delete_whoop_credentials(self, user_id):
        """Delete WHOOP credentials for a user."""
        return self._whoop_ops.delete_whoop_credentials(user_id)

    def refresh_whoop_token_if_needed(self, user_id):
        """Check if WHOOP token is expired and refresh if needed."""
        return self._whoop_ops.refresh_whoop_token_if_needed(user_id)

    def get_whoop_settings(self, user_id):
        """Get WHOOP notification settings."""
        return self._whoop_ops.get_whoop_settings(user_id)

    def update_whoop_settings(self, user_id, settings):
        """Update WHOOP notification settings."""
        return self._whoop_ops.update_whoop_settings(user_id, settings)

    def track_whoop_data(self, user_id, data_type, whoop_id):
        """Track processed WHOOP record."""
        return self._whoop_ops.track_whoop_data(user_id, data_type, whoop_id)

    def is_whoop_data_tracked(self, whoop_id):
        """Check if WHOOP record already processed."""
        return self._whoop_ops.is_whoop_data_tracked(whoop_id)

    def get_tracked_whoop_data(self, user_id, data_type=None, days=7):
        """Get list of tracked WHOOP IDs."""
        return self._whoop_ops.get_tracked_whoop_data(user_id, data_type, days)

    def cleanup_old_whoop_tracking(self, days=7):
        """Delete old WHOOP tracking records."""
        return self._whoop_ops.cleanup_old_whoop_tracking(days)

    def delete_all_whoop_data(self, user_id):
        """Delete all WHOOP data for a user."""
        return self._whoop_ops.delete_all_whoop_data(user_id)

    # =============================
    # Plex Operations (delegated)
    # =============================

    def store_plex_credentials(self, user_id, access_token, plex_user_id,
                                plex_username, server_url, server_name=None, server_version=None):
        """Store Plex OAuth credentials."""
        return self._plex_ops.store_plex_credentials(
            user_id, access_token, plex_user_id, plex_username,
            server_url, server_name, server_version
        )

    def get_plex_credentials(self, user_id):
        """Get Plex credentials for a user."""
        return self._plex_ops.get_plex_credentials(user_id)

    def update_plex_credentials(self, user_id, **kwargs):
        """Update Plex credentials (partial update)."""
        return self._plex_ops.update_plex_credentials(user_id, **kwargs)

    def update_plex_server_url(self, user_id, server_url):
        """Update Plex server URL."""
        return self._plex_ops.update_plex_credentials(user_id, server_url=server_url)

    def invalidate_plex_credentials(self, user_id, error_message):
        """Mark Plex credentials as invalid."""
        return self._plex_ops.invalidate_plex_credentials(user_id, error_message)

    def delete_plex_credentials(self, user_id):
        """Delete Plex credentials for a user."""
        return self._plex_ops.delete_plex_credentials(user_id)

    def get_plex_settings(self, user_id):
        """Get Plex notification settings."""
        return self._plex_ops.get_plex_settings(user_id)

    def update_plex_settings(self, user_id, **kwargs):
        """Update Plex notification settings."""
        return self._plex_ops.update_plex_settings(user_id, **kwargs)

    def delete_plex_settings(self, user_id):
        """Delete Plex settings for a user."""
        return self._plex_ops.delete_plex_settings(user_id)

    def is_plex_item_notified(self, user_id, plex_item_key):
        """Check if user has been notified about a Plex item."""
        return self._plex_ops.is_plex_item_notified(user_id, plex_item_key)

    def track_plex_notification(self, user_id, plex_item_key, plex_item_type):
        """Track that user was notified about a Plex item."""
        return self._plex_ops.track_plex_notification(user_id, plex_item_key, plex_item_type)

    def cleanup_old_plex_tracking(self, days=7):
        """Delete old Plex tracking records."""
        return self._plex_ops.cleanup_old_plex_tracking(days)

    def delete_all_plex_tracking(self, user_id):
        """Delete all Plex tracking for a user."""
        return self._plex_ops.delete_all_plex_tracking(user_id)

    # =============================
    # Action Operations (delegated)
    # =============================

    def create_action(self, user_id, session_id, action_type, category,
                      intent_summary, service_provider_id=None, **kwargs):
        """Create a new action."""
        return self._action_ops.create_action(
            user_id, session_id, action_type, category,
            intent_summary, service_provider_id, **kwargs
        )

    def get_action(self, action_id):
        """Get an action by ID."""
        return self._action_ops.get_action(action_id)

    def get_pending_actions(self, user_id):
        """Get all pending actions for a user."""
        return self._action_ops.get_pending_actions(user_id)

    def update_action_status(self, action_id, status, **kwargs):
        """Update action status and related fields."""
        return self._action_ops.update_action_status(action_id, status, **kwargs)

    def get_action_by_id(self, action_id):
        """Get an action by ID (alias for get_action)."""
        return self._action_ops.get_action_by_id(action_id)

    # =============================
    # Confirmation Operations (delegated)
    # =============================

    def create_confirmation(self, action_id, confirmation_message, expires_at):
        """Create a confirmation request for an action."""
        return self._action_ops.create_confirmation(action_id, confirmation_message, expires_at)

    def get_pending_confirmations(self, user_id):
        """Get all pending confirmations for a user."""
        return self._action_ops.get_pending_confirmations(user_id)

    def update_confirmation_response(self, action_id, user_response, user_response_text=None):
        """Update confirmation with user response."""
        return self._action_ops.update_confirmation_response(action_id, user_response, user_response_text)

    def get_confirmation_by_id(self, confirmation_id):
        """Get a confirmation by ID with computed status."""
        return self._action_ops.get_confirmation_by_id(confirmation_id)

    def update_confirmation_status(self, confirmation_id, status, **kwargs):
        """Update confirmation status."""
        return self._action_ops.update_confirmation_status(confirmation_id, status, **kwargs)

    def update_turn_metadata(self, session_id, confirmation_id, approved):
        """Update the metadata of a turn to reflect approval/rejection status."""
        return self._action_ops.update_turn_metadata(session_id, confirmation_id, approved)

    # =============================
    # Classification Audit Operations
    # =============================

    def log_classification_audit(self, user_id, classification, action, session_id=None, justification=None):
        """
        Log a classification-related action for OFFICIAL compliance.

        Args:
            user_id: ID of user performing the action
            classification: Classification level (e.g., 'OFFICIAL')
            action: Type of action ('create', 'export', 'update', 'access')
            session_id: Optional session ID if action is session-specific
            justification: Optional justification text

        Returns:
            ID of the created audit log entry
        """
        with self._get_connection() as conn:
            from sqlalchemy import insert
            from datetime import datetime

            stmt = insert(self.classification_audit).values(
                user_id=user_id,
                session_id=session_id,
                classification=classification,
                action=action,
                justification=justification,
                timestamp=datetime.utcnow()
            )

            result = conn.execute(stmt)
            return result.lastrowid

    def _get_connection(self):
        """Get a database connection context manager."""
        from contextlib import contextmanager

        @contextmanager
        def connection():
            session = self.Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        return connection()

    # =============================
    # Voice Operations (delegated)
    # =============================

    def log_tts_usage(self, model, character_count, estimated_cost, success=True, error_message=None):
        """Log TTS usage."""
        return self._voice_ops.log_tts_usage(model, character_count, estimated_cost, success, error_message)

    def log_stt_usage(self, model, audio_duration_seconds, estimated_cost, success=True, error_message=None):
        """Log STT usage."""
        return self._voice_ops.log_stt_usage(model, audio_duration_seconds, estimated_cost, success, error_message)

    def get_voice_costs(self, days=30):
        """Get voice service costs."""
        return self._voice_ops.get_voice_costs(days)

    # =============================
    # User Preferences
    # =============================

    def get_user_preference(self, user_id, key, default=None):
        """
        Get a user preference value.

        Args:
            user_id: User identifier
            key: Preference key
            default: Default value if preference doesn't exist

        Returns:
            Preference value or default
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.preferences)
                .where(self.preferences.c.user_id == user_id)
                .where(self.preferences.c.key == key)
            ).fetchone()
            return row.value if row else default

    def set_user_preference(self, user_id, key, value):
        """
        Set a user preference value.

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value
        """
        from sqlalchemy import insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with self._get_connection() as conn:
            # Use INSERT OR REPLACE for SQLite (upsert)
            stmt = sqlite_insert(self.preferences).values(
                user_id=user_id,
                key=key,
                value=value,
                updated_at=datetime.utcnow()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id', 'key'],
                set_={
                    'value': value,
                    'updated_at': datetime.utcnow()
                }
            )
            conn.execute(stmt)

    def delete_user_preference(self, user_id, key):
        """
        Delete a user preference.

        Args:
            user_id: User identifier
            key: Preference key to delete
        """
        from sqlalchemy import delete

        with self._get_connection() as conn:
            stmt = delete(self.preferences).where(
                (self.preferences.c.user_id == user_id) &
                (self.preferences.c.key == key)
            )
            conn.execute(stmt)

    # ==============================
    # Routine Operations (delegated)
    # ==============================

    def get_user_routines(self, user_id):
        """Get all routines for a user."""
        return self._routine_ops.get_user_routines(user_id)

    def get_user_routine(self, routine_id, user_id):
        """Get a specific routine."""
        return self._routine_ops.get_user_routine(routine_id, user_id)

    def create_user_routine(self, user_id, name, triggers, actions, consolidation_prompt=""):
        """Create a new user routine."""
        return self._routine_ops.create_user_routine(
            user_id, name, triggers, actions, consolidation_prompt
        )

    def update_user_routine(self, routine_id, user_id, name=None, triggers=None,
                           actions=None, consolidation_prompt=None, enabled=None):
        """Update a user routine."""
        return self._routine_ops.update_user_routine(
            routine_id, user_id, name, triggers, actions, consolidation_prompt, enabled
        )

    def delete_user_routine(self, routine_id, user_id):
        """Delete a user routine."""
        return self._routine_ops.delete_user_routine(routine_id, user_id)

    # =============================
    # OAuth Configuration Storage
    # =============================

    def store_oauth_config(self, user_id, provider_type, provider_name, config):
        """
        Store OAuth configuration for a provider.

        Args:
            user_id: User ID
            provider_type: Type of provider (e.g., 'whoop', 'm365')
            provider_name: Display name for provider
            config: Dict with OAuth credentials (will be encrypted)

        Returns:
            int: Provider ID
        """
        from utils.encryption import encrypt_oauth_config

        with self.engine.begin() as conn:
            # Encrypt the config
            encrypted_config = encrypt_oauth_config(config)

            # Check if provider exists
            existing = conn.execute(
                select(self.feature_providers.c.id)
                .where(self.feature_providers.c.user_id == user_id)
                .where(self.feature_providers.c.provider_type == provider_type)
            ).fetchone()

            if existing:
                # Update existing
                conn.execute(
                    update(self.feature_providers)
                    .where(self.feature_providers.c.id == existing[0])
                    .values(
                        encrypted_config=encrypted_config,
                        updated_at=datetime.utcnow()
                    )
                )
                return existing[0]
            else:
                # Insert new
                result = conn.execute(
                    insert(self.feature_providers).values(
                        user_id=user_id,
                        provider_type=provider_type,
                        provider_name=provider_name,
                        is_enabled=True,
                        encrypted_config=encrypted_config,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                return result.inserted_primary_key[0]

    def get_oauth_config(self, user_id, provider_type):
        """
        Get OAuth configuration for a provider.

        Args:
            user_id: User ID
            provider_type: Type of provider (e.g., 'whoop', 'm365')

        Returns:
            dict: Decrypted OAuth config or None if not found
        """
        from utils.encryption import decrypt_oauth_config

        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.feature_providers)
                .where(self.feature_providers.c.user_id == user_id)
                .where(self.feature_providers.c.provider_type == provider_type)
            ).fetchone()

            if not row or not row.encrypted_config:
                return None

            try:
                return decrypt_oauth_config(row.encrypted_config)
            except Exception:
                # Config is corrupted or key changed
                return None

    def delete_oauth_config(self, user_id, provider_type):
        """
        Delete OAuth configuration for a provider.

        Args:
            user_id: User ID
            provider_type: Type of provider (e.g., 'whoop', 'm365')
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.feature_providers)
                .where(self.feature_providers.c.user_id == user_id)
                .where(self.feature_providers.c.provider_type == provider_type)
            )

    # =============================
    # Intent Reasoning Operations
    # =============================

    def store_reasoning_trace(
        self,
        user_id: int,
        reasoning_result,
        session_id: str = None,
        mode: str = None,
        subtab: str = None,
        user_text: str = None
    ) -> int:
        """
        Store an intent reasoning trace for debugging and analysis.

        Args:
            user_id: User ID
            reasoning_result: IntentReasoningResult object
            session_id: Optional session ID
            mode: Optional mode (personal/work)
            subtab: Optional subtab
            user_text: Original user input text

        Returns:
            int: ID of the created trace record
        """
        import json
        from sqlalchemy import text

        with self.engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO intent_reasoning_traces
                    (user_id, session_id, user_text, mode, subtab, intent, confidence,
                     reasoning, entities, service_signals, parameters, is_ambiguous,
                     clarification_question, token_count, latency_ms, source)
                    VALUES
                    (:user_id, :session_id, :user_text, :mode, :subtab, :intent, :confidence,
                     :reasoning, :entities, :service_signals, :parameters, :is_ambiguous,
                     :clarification_question, :token_count, :latency_ms, :source)
                """),
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "user_text": user_text,
                    "mode": mode,
                    "subtab": subtab,
                    "intent": reasoning_result.intent,
                    "confidence": reasoning_result.confidence,
                    "reasoning": reasoning_result.reasoning,
                    "entities": json.dumps(reasoning_result.entities.__dict__ if hasattr(reasoning_result.entities, '__dict__') else {}),
                    "service_signals": json.dumps([{"service": s.service, "relevance": s.relevance, "reason": s.reason} for s in reasoning_result.service_signals]),
                    "parameters": json.dumps(reasoning_result.parameters),
                    "is_ambiguous": 1 if reasoning_result.is_ambiguous else 0,
                    "clarification_question": reasoning_result.clarification_question,
                    "token_count": reasoning_result.token_count,
                    "latency_ms": reasoning_result.latency_ms,
                    "source": reasoning_result.source
                }
            )
            return result.lastrowid

    def get_reasoning_traces(
        self,
        user_id: int,
        limit: int = 100,
        intent_filter: str = None,
        source_filter: str = None
    ):
        """
        Retrieve reasoning traces for analysis.

        Args:
            user_id: User ID
            limit: Maximum number of traces to return (default: 100)
            intent_filter: Optional filter by intent
            source_filter: Optional filter by source (reasoning/fallback/cache)

        Returns:
            List[dict]: List of trace records
        """
        from sqlalchemy import text

        query = """
            SELECT * FROM intent_reasoning_traces
            WHERE user_id = :user_id
        """
        params = {"user_id": user_id, "limit": limit}

        if intent_filter:
            query += " AND intent = :intent"
            params["intent"] = intent_filter

        if source_filter:
            query += " AND source = :source"
            params["source"] = source_filter

        query += " ORDER BY created_at DESC LIMIT :limit"

        with self.engine.begin() as conn:
            result = conn.execute(text(query), params)
            return [dict(row._mapping) for row in result]
