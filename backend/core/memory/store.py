"""
Main MemoryStore class.

Delegates to specialized operation modules using a clean modular architecture.
All table definitions are centralized in schema.py.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker

from .schema import create_schema
from .memories import MemoryOperations
from .intents import IntentOperations
from .sessions import SessionOperations
from .providers import ProviderOperations
from .users import UserOperations
from .modes import ModeOperations
from .service_providers import ServiceProviderOperations
from .m365 import M365Operations
from .actions import ActionOperations


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
        self.engine = create_engine(db_url)
        self.meta = MetaData()

        # Create all table definitions from centralized schema
        tables = create_schema(self.meta)

        # Assign tables as instance attributes for compatibility
        self.users = tables["users"]
        self.auth_sessions = tables["auth_sessions"]
        self.user_mode_config = tables["user_mode_config"]
        self.mode_settings = tables["mode_settings"]
        self.work_mode_subtab_config = tables["work_mode_subtab_config"]
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

        # Create all tables
        self.meta.create_all(self.engine)

        # Create session maker
        self.Session = sessionmaker(bind=self.engine)

        # Initialize specialized operation modules
        self._memory_ops = MemoryOperations(tables, self.Session, self.engine)
        self._intent_ops = IntentOperations(tables, self.Session, self.engine)
        self._session_ops = SessionOperations(tables, self.Session, self.engine)
        self._provider_ops = ProviderOperations(tables, self.Session, self.engine)
        self._user_ops = UserOperations(tables, self.Session, self.engine)
        self._mode_ops = ModeOperations(tables, self.Session, self.engine)
        self._service_provider_ops = ServiceProviderOperations(tables, self.Session, self.engine)
        self._m365_ops = M365Operations(tables, self.Session, self.engine)
        self._action_ops = ActionOperations(tables, self.Session, self.engine)

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

    def set_routing_preference(self, user_id, intent, provider_id):
        """Set routing preference for an intent."""
        return self._intent_ops.set_routing_preference(user_id, intent, provider_id)

    def get_routing_preferences(self, user_id):
        """Get all routing preferences for a user."""
        return self._intent_ops.get_routing_preferences(user_id)

    def delete_routing_preference(self, user_id, intent):
        """Delete a routing preference."""
        return self._intent_ops.delete_routing_preference(user_id, intent)

    def get_routing_provider(self, user_id, intent):
        """Get provider ID for a specific intent."""
        return self._intent_ops.get_routing_provider(user_id, intent)

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

    def save_turn(self, session_id, role, content, created_at=None, provider_id=None, model=None, intent=None, metadata=None, mode="personal", user_id=None):
        """Save a conversation turn (message)."""
        return self._session_ops.save_turn(session_id, role, content, created_at, provider_id, model, intent, metadata, mode, user_id)

    def get_recent_turns(self, session_id, limit=6):
        """Get recent conversation turns for a session."""
        return self._session_ops.get_recent_turns(session_id, limit)

    def build_context(self, session_id, system_prompt, limit=12):
        """Build deterministic context for model invocation."""
        return self._session_ops.build_context(session_id, system_prompt, limit)

    def update_turn_metadata(self, session_id, role, metadata):
        """Update metadata for the most recent turn matching session_id and role."""
        return self._session_ops.update_turn_metadata(session_id, role, metadata)

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

    def create_user(self, username, password_hash, is_admin=False):
        """Create a new user."""
        return self._user_ops.create_user(username, password_hash, is_admin)

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

    def create_auth_session(self, session_id, user_id, expires_at):
        """Create an authentication session."""
        return self._user_ops.create_auth_session(session_id, user_id, expires_at)

    def get_auth_session(self, session_id):
        """Get authentication session."""
        return self._user_ops.get_auth_session(session_id)

    def delete_auth_session(self, session_id):
        """Delete authentication session (logout)."""
        return self._user_ops.delete_auth_session(session_id)

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
