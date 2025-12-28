"""
Mode operations module.

Handles:
- Work/Personal mode configuration
- Mode-specific settings (system prompts, providers, tone)
- Work mode subtab configuration (conversation, email, code)
"""

from datetime import datetime
from sqlalchemy import select, delete, insert, update

from .base import BaseMemoryOperations


class ModeOperations(BaseMemoryOperations):
    """Operations for managing work/personal modes and their settings."""

    # =============================
    # Mode Configuration
    # =============================

    def get_user_mode(self, user_id):
        """
        Get user's active mode.

        Args:
            user_id: User identifier

        Returns:
            Mode config dictionary with active_mode
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.user_mode_config)
                .where(self.user_mode_config.c.user_id == user_id)
            ).fetchone()

            if row:
                return dict(row._mapping)

            # Create default if not exists
            conn.execute(
                insert(self.user_mode_config).values(
                    user_id=user_id,
                    active_mode="personal",
                    updated_at=datetime.utcnow(),
                )
            )
            return {"user_id": user_id, "active_mode": "personal"}

    def set_user_mode(self, user_id, mode):
        """
        Set user's active mode.

        Args:
            user_id: User identifier
            mode: Mode to activate ("work" or "personal")
        """
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.user_mode_config)
                .where(self.user_mode_config.c.user_id == user_id)
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.user_mode_config)
                    .where(self.user_mode_config.c.user_id == user_id)
                    .values(
                        active_mode=mode,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    insert(self.user_mode_config).values(
                        user_id=user_id,
                        active_mode=mode,
                        updated_at=datetime.utcnow(),
                    )
                )

    # =============================
    # Mode Settings
    # =============================

    def get_mode_settings(self, user_id, mode):
        """
        Get settings for a specific mode.

        Args:
            user_id: User identifier
            mode: Mode name ("work" or "personal")

        Returns:
            Mode settings dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
                .where(self.mode_settings.c.mode == mode)
            ).fetchone()
            return dict(row._mapping) if row else None

    def create_or_update_mode_settings(self, user_id, mode, system_prompt_override=None,
                                       preferred_provider_id=None, tone=None):
        """
        Create or update mode settings.

        Args:
            user_id: User identifier
            mode: Mode name ("work" or "personal")
            system_prompt_override: Optional custom system prompt
            preferred_provider_id: Optional preferred AI provider ID
            tone: Optional tone setting (e.g., "professional", "casual")
        """
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
                .where(self.mode_settings.c.mode == mode)
            ).fetchone()

            values = {
                "updated_at": datetime.utcnow(),
            }

            if system_prompt_override is not None:
                values["system_prompt_override"] = system_prompt_override
            if preferred_provider_id is not None:
                values["preferred_provider_id"] = preferred_provider_id
            if tone is not None:
                values["tone"] = tone

            if existing:
                conn.execute(
                    update(self.mode_settings)
                    .where(self.mode_settings.c.user_id == user_id)
                    .where(self.mode_settings.c.mode == mode)
                    .values(**values)
                )
            else:
                values.update({
                    "user_id": user_id,
                    "mode": mode,
                    "created_at": datetime.utcnow(),
                })
                if "system_prompt_override" not in values:
                    values["system_prompt_override"] = None
                if "preferred_provider_id" not in values:
                    values["preferred_provider_id"] = None
                if "tone" not in values:
                    values["tone"] = "neutral"

                conn.execute(
                    insert(self.mode_settings).values(**values)
                )

    def get_all_mode_settings(self, user_id):
        """
        Get all mode settings for a user.

        Args:
            user_id: User identifier

        Returns:
            List of mode settings dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    # =============================
    # Work Mode Subtab Configuration
    # =============================

    def get_work_subtab_config(self, user_id, subtab):
        """
        Get configuration for a specific work subtab.

        Args:
            user_id: User identifier
            subtab: Subtab name ("conversation", "email", "code")

        Returns:
            Subtab config dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
                .where(self.work_mode_subtab_config.c.subtab == subtab)
            ).fetchone()
            return dict(row._mapping) if row else None

    def update_work_subtab_config(self, user_id, subtab, config_json):
        """
        Update configuration for a specific work subtab.

        Args:
            user_id: User identifier
            subtab: Subtab name ("conversation", "email", "code")
            config_json: JSON string with subtab-specific configuration
        """
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
                .where(self.work_mode_subtab_config.c.subtab == subtab)
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.work_mode_subtab_config)
                    .where(self.work_mode_subtab_config.c.user_id == user_id)
                    .where(self.work_mode_subtab_config.c.subtab == subtab)
                    .values(
                        config_json=config_json,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    insert(self.work_mode_subtab_config).values(
                        user_id=user_id,
                        subtab=subtab,
                        config_json=config_json,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def get_all_work_subtab_configs(self, user_id):
        """
        Get all work subtab configurations for a user.

        Args:
            user_id: User identifier

        Returns:
            List of subtab config dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]
