"""
Provider operations module.

Handles:
- Provider CRUD operations
- Provider metadata and health monitoring
- Request logging and cost estimation
- Session provider tracking
"""

from datetime import datetime
import logging
from sqlalchemy import select, delete, insert, update, func

from .base import BaseMemoryOperations


class ProviderOperations(BaseMemoryOperations):
    """Operations for managing AI providers and their metadata."""

    # =============================
    # Provider CRUD
    # =============================

    def list_providers(self):
        """
        Get all providers.

        Returns:
            List of provider dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(select(self.providers)).fetchall()
            return [dict(row._mapping) for row in rows]

    def get_provider(self, provider_id):
        """
        Get a specific provider by ID.

        Args:
            provider_id: Provider identifier

        Returns:
            Provider dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.providers)
                .where(self.providers.c.id == provider_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def upsert_provider(self, provider):
        """
        Insert or update a provider.

        Args:
            provider: Dictionary with provider data (id, name, type, base_url, model, api_key, enabled)
        """
        with self._get_connection() as conn:
            existing = conn.execute(
                select(self.providers.c.id)
                .where(self.providers.c.id == provider["id"])
            ).fetchone()

            if existing:
                # Build update values - preserve existing api_key if not provided
                update_values = {
                    "name": provider["name"],
                    "type": provider["type"],
                    "base_url": provider.get("base_url"),
                    "model": provider.get("model"),
                    "enabled": provider.get("enabled", True),
                    "updated_at": datetime.utcnow(),
                }

                # Only update api_key if it's explicitly provided
                if "api_key" in provider:
                    update_values["api_key"] = provider["api_key"]

                conn.execute(
                    update(self.providers)
                    .where(self.providers.c.id == provider["id"])
                    .values(**update_values)
                )
            else:
                conn.execute(
                    insert(self.providers).values(
                        id=provider["id"],
                        name=provider["name"],
                        type=provider["type"],
                        base_url=provider.get("base_url"),
                        model=provider.get("model"),
                        api_key=provider.get("api_key"),
                        enabled=provider.get("enabled", True),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def delete_provider(self, provider_id):
        """
        Delete a provider.

        Args:
            provider_id: Provider identifier
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.providers)
                .where(self.providers.c.id == provider_id)
            )

    # =============================
    # Provider Metadata & Intelligence
    # =============================

    def init_provider_metadata(self, provider_id, cost_per_1k_input=0, cost_per_1k_output=0):
        """
        Initialize or update provider metadata with cost data.

        Args:
            provider_id: Provider identifier
            cost_per_1k_input: Cost per 1K input tokens in micro-dollars (1/1,000,000 of $1)
            cost_per_1k_output: Cost per 1K output tokens in micro-dollars
        """
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with self._get_connection() as conn:
            existing = conn.execute(
                select(self.provider_metadata.c.provider_id)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()

            if not existing:
                # Create new metadata entry
                conn.execute(
                    insert(self.provider_metadata).values(
                        provider_id=provider_id,
                        cost_per_1k_input_tokens=cost_per_1k_input,
                        cost_per_1k_output_tokens=cost_per_1k_output,
                        avg_latency_ms=0,
                        total_requests=0,
                        failed_requests=0,
                        health_status="unknown",
                        circuit_breaker_open=False,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                # Update existing metadata's cost fields
                from sqlalchemy import update
                conn.execute(
                    update(self.provider_metadata)
                    .where(self.provider_metadata.c.provider_id == provider_id)
                    .values(
                        cost_per_1k_input_tokens=cost_per_1k_input,
                        cost_per_1k_output_tokens=cost_per_1k_output,
                        updated_at=datetime.utcnow(),
                    )
                )

    def get_provider_metadata(self, provider_id):
        """
        Get metadata for a specific provider.

        Args:
            provider_id: Provider identifier

        Returns:
            Metadata dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_all_provider_metadata(self):
        """
        Get metadata for all providers.

        Returns:
            Dictionary mapping provider_id to metadata dict
        """
        with self._get_connection() as conn:
            rows = conn.execute(select(self.provider_metadata)).fetchall()
            return {row.provider_id: dict(row._mapping) for row in rows}

    def log_request(self, session_id, provider_id, intent, success, latency_ms,
                   input_tokens=0, output_tokens=0, estimated_cost=0, error_message=None):
        """
        Log a provider request for analytics and health tracking.

        Args:
            session_id: Session identifier
            provider_id: Provider identifier
            intent: Intent type
            success: Whether request succeeded
            latency_ms: Request latency in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost: Estimated cost in micro-dollars
            error_message: Error message if failed
        """
        with self._get_connection() as conn:
            conn.execute(
                insert(self.request_logs).values(
                    session_id=session_id,
                    provider_id=provider_id,
                    intent=intent,
                    success=success,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    error_message=error_message,
                    created_at=datetime.utcnow(),
                )
            )

    def update_provider_health(self, provider_id, success, latency_ms=None):
        """
        Update provider health metrics based on request outcome.

        Args:
            provider_id: Provider identifier
            success: Whether request succeeded
            latency_ms: Request latency in milliseconds (optional)
        """
        with self._get_connection() as conn:
            # Get current metadata
            metadata = conn.execute(
                select(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()

            if not metadata:
                # Initialize if doesn't exist
                self.init_provider_metadata(provider_id)
                metadata = conn.execute(
                    select(self.provider_metadata)
                    .where(self.provider_metadata.c.provider_id == provider_id)
                ).fetchone()

            now = datetime.utcnow()
            total = metadata.total_requests + 1
            failed = metadata.failed_requests + (0 if success else 1)

            # Calculate rolling average latency
            if latency_ms and success:
                current_avg = metadata.avg_latency_ms or 0
                current_count = metadata.total_requests
                new_avg = ((current_avg * current_count) + latency_ms) / total
            else:
                new_avg = metadata.avg_latency_ms

            # Determine health status
            failure_rate = failed / total if total > 0 else 0

            if total < 5:
                health_status = "unknown"
            elif failure_rate > 0.5:
                health_status = "unhealthy"
            elif failure_rate > 0.2:
                health_status = "degraded"
            else:
                health_status = "healthy"

            # Circuit breaker logic: open if 5+ consecutive failures
            recent_failures = conn.execute(
                select(func.count(self.request_logs.c.id))
                .where(self.request_logs.c.provider_id == provider_id)
                .where(self.request_logs.c.success == False)
                .order_by(self.request_logs.c.created_at.desc())
                .limit(5)
            ).scalar()

            circuit_breaker_open = recent_failures >= 5

            conn.execute(
                update(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
                .values(
                    total_requests=total,
                    failed_requests=failed,
                    avg_latency_ms=int(new_avg),
                    last_success_at=now if success else metadata.last_success_at,
                    last_failure_at=now if not success else metadata.last_failure_at,
                    health_status=health_status,
                    circuit_breaker_open=circuit_breaker_open,
                    updated_at=now,
                )
            )

    def get_provider_health_summary(self):
        """
        Get health summary for all providers.

        Returns:
            Dictionary mapping provider_id to health summary dict
        """
        with self._get_connection() as conn:
            rows = conn.execute(select(self.provider_metadata)).fetchall()

            summary = {}
            for row in rows:
                failure_rate = row.failed_requests / row.total_requests if row.total_requests > 0 else 0
                summary[row.provider_id] = {
                    "health_status": row.health_status,
                    "circuit_breaker_open": row.circuit_breaker_open,
                    "total_requests": row.total_requests,
                    "failure_rate": round(failure_rate * 100, 2),
                    "avg_latency_ms": row.avg_latency_ms,
                    "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
                    "last_failure_at": row.last_failure_at.isoformat() if row.last_failure_at else None,
                }

            return summary

    def reset_provider_health(self, provider_id):
        """
        Reset health metrics for a provider to healthy state.
        Clears failure counts, circuit breaker, and sets status to healthy.

        Args:
            provider_id: Provider identifier
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
                .values(
                    total_requests=0,
                    failed_requests=0,
                    health_status="healthy",
                    circuit_breaker_open=False,
                    updated_at=datetime.utcnow(),
                )
            )
            conn.commit()

    def estimate_cost(self, provider_id, input_tokens, output_tokens):
        """
        Estimate cost for a request in micro-dollars.

        Args:
            provider_id: Provider identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in micro-dollars
        """
        metadata = self.get_provider_metadata(provider_id)
        if not metadata:
            return 0

        input_cost = (input_tokens / 1000) * metadata["cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * metadata["cost_per_1k_output_tokens"]

        return int(input_cost + output_cost)

    def get_provider_costs(self, days=30):
        """
        Calculate total costs for all providers over the specified period.

        Args:
            days: Number of days to look back (7, 30, 90, or None for all-time)

        Returns:
            Dictionary with provider costs and totals
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func

        with self._get_connection() as conn:
            # Build query with optional date filter
            query = select(
                self.request_logs.c.provider_id,
                func.sum(self.request_logs.c.input_tokens).label("total_input_tokens"),
                func.sum(self.request_logs.c.output_tokens).label("total_output_tokens"),
                func.sum(self.request_logs.c.estimated_cost).label("total_cost_microdollars"),
                func.count(self.request_logs.c.id).label("request_count")
            ).group_by(self.request_logs.c.provider_id)

            # Apply date filter if specified
            if days is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = query.where(self.request_logs.c.created_at >= cutoff_date)

            rows = conn.execute(query).fetchall()

            # Build response
            providers = []
            total_cost_usd = 0.0

            for row in rows:
                cost_usd = row.total_cost_microdollars / 1_000_000 if row.total_cost_microdollars else 0.0
                total_cost_usd += cost_usd

                # Get provider name
                provider_info = self.get_provider(row.provider_id)
                provider_name = provider_info.get("name", row.provider_id) if provider_info else row.provider_id

                providers.append({
                    "provider_id": row.provider_id,
                    "name": provider_name,
                    "total_cost_usd": round(cost_usd, 6),
                    "input_tokens_total": row.total_input_tokens or 0,
                    "output_tokens_total": row.total_output_tokens or 0,
                    "request_count": row.request_count or 0
                })

            return {
                "providers": providers,
                "total_cost_usd": round(total_cost_usd, 6),
                "period_days": days
            }

    def delete_provider_metadata(self, provider_id):
        """
        Delete provider metadata and request logs when provider is removed.

        Args:
            provider_id: Provider identifier
        """
        with self._get_connection() as conn:
            # Delete metadata
            conn.execute(
                delete(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            )

            # Delete request logs
            conn.execute(
                delete(self.request_logs)
                .where(self.request_logs.c.provider_id == provider_id)
            )

    # =============================
    # Session Provider Tracking
    # =============================

    def set_last_provider(self, session_id, provider_id):
        """
        Set the last provider used for a session.

        Args:
            session_id: Session identifier
            provider_id: Provider identifier
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.session_providers)
                .where(self.session_providers.c.session_id == session_id)
            )
            conn.execute(
                insert(self.session_providers).values(
                    session_id=session_id,
                    provider_id=provider_id,
                    updated_at=datetime.utcnow(),
                )
            )

    def get_last_provider(self, session_id):
        """
        Get the last provider used for a session.

        Args:
            session_id: Session identifier

        Returns:
            Provider ID or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.session_providers.c.provider_id)
                .where(self.session_providers.c.session_id == session_id)
            ).fetchone()
            return row.provider_id if row else None
