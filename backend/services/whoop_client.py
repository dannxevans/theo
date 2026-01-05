"""
WHOOP API Client

Handles all interactions with WHOOP API v1.
Reference: https://developer.whoop.com/api
"""

import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WHOOPClient:
    """Client for WHOOP API v1."""

    BASE_URL = 'https://api.prod.whoop.com/developer/v1'

    def __init__(self, access_token: str):
        """
        Initialize WHOOP client with access token.

        Args:
            access_token: OAuth access token
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        })

    def get_user_profile(self) -> Dict:
        """
        Get user profile information.

        Returns:
            dict: User profile data including user_id, email, etc.

        Raises:
            requests.HTTPError: If API call fails
        """
        try:
            response = self.session.get(f'{self.BASE_URL}/user/profile/basic', timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"[WHOOP_CLIENT] Failed to fetch user profile: {e}")
            raise

    def get_sleep_collection(self, start: str = None, end: str = None, limit: int = 25) -> Dict:
        """
        Get sleep records.

        Args:
            start: ISO 8601 timestamp (default: 7 days ago)
            end: ISO 8601 timestamp (default: now)
            limit: Max records to return (default: 25, max: 50)

        Returns:
            dict: Sleep collection with 'records' array

        Raises:
            requests.HTTPError: If API call fails
        """
        params = {'limit': min(limit, 50)}
        if start:
            params['start'] = start
        if end:
            params['end'] = end

        try:
            response = self.session.get(f'{self.BASE_URL}/activity/sleep', params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"[WHOOP_CLIENT] Failed to fetch sleep data: {e}")
            raise


    def get_workout_collection(self, start: str = None, end: str = None, limit: int = 25) -> Dict:
        """
        Get workout records.

        Args:
            start: ISO 8601 timestamp (default: 7 days ago)
            end: ISO 8601 timestamp (default: now)
            limit: Max records to return (default: 25, max: 50)

        Returns:
            dict: Workout collection with 'records' array

        Raises:
            requests.HTTPError: If API call fails
        """
        params = {'limit': min(limit, 50)}
        if start:
            params['start'] = start
        if end:
            params['end'] = end

        try:
            response = self.session.get(f'{self.BASE_URL}/activity/workout', params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"[WHOOP_CLIENT] Failed to fetch workout data: {e}")
            raise

    def get_cycle_collection(self, start: str = None, end: str = None, limit: int = 25) -> Dict:
        """
        Get physiological cycles (strain data).
        A cycle starts when you wake up and ends when you wake up the next day.

        Args:
            start: ISO 8601 timestamp (default: 7 days ago)
            end: ISO 8601 timestamp (default: now)
            limit: Max records to return (default: 25, max: 50)

        Returns:
            dict: Cycle collection with 'records' array

        Raises:
            requests.HTTPError: If API call fails
        """
        params = {'limit': min(limit, 50)}
        if start:
            params['start'] = start
        if end:
            params['end'] = end

        try:
            response = self.session.get(f'{self.BASE_URL}/cycle', params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"[WHOOP_CLIENT] Failed to fetch cycle data: {e}")
            raise

    def get_latest_sleep(self) -> Optional[Dict]:
        """
        Get the most recent sleep record.

        Returns:
            dict: Latest sleep record or None if no recent sleep found

        Raises:
            requests.HTTPError: If API call fails
        """
        # Get last 24 hours
        end = datetime.utcnow().isoformat() + 'Z'
        start = (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'

        data = self.get_sleep_collection(start=start, end=end, limit=1)
        records = data.get('records', [])
        return records[0] if records else None

    def get_latest_workout(self) -> Optional[Dict]:
        """
        Get the most recent workout record.

        Returns:
            dict: Latest workout record or None if no recent workout found

        Raises:
            requests.HTTPError: If API call fails
        """
        # Get last 12 hours
        end = datetime.utcnow().isoformat() + 'Z'
        start = (datetime.utcnow() - timedelta(hours=12)).isoformat() + 'Z'

        data = self.get_workout_collection(start=start, end=end, limit=1)
        records = data.get('records', [])
        return records[0] if records else None

    def get_latest_recovery(self) -> Optional[Dict]:
        """
        Get the most recent recovery record.
        Recovery includes HRV and resting heart rate used for stress calculations.

        In WHOOP API v1, recovery data is embedded within cycle data.

        Returns:
            dict: Latest recovery record or None if no recent recovery found

        Raises:
            requests.HTTPError: If API call fails
        """
        # Get recent cycles (last 2 days to ensure we have data)
        end = datetime.utcnow().isoformat() + 'Z'
        start = (datetime.utcnow() - timedelta(days=2)).isoformat() + 'Z'

        logger.info(f"[WHOOP_CLIENT] Fetching cycles from {start} to {end} for recovery data")

        cycle_data = self.get_cycle_collection(start=start, end=end, limit=10)
        cycles = cycle_data.get('records', [])

        logger.info(f"[WHOOP_CLIENT] Found {len(cycles)} cycles")

        if not cycles:
            logger.info("[WHOOP_CLIENT] No recent cycles found")
            return None

        # Look for cycles with recovery data (recovery is embedded in cycle response)
        for i, cycle in enumerate(cycles):
            # Recovery data is in the 'score' field of the cycle
            recovery_score = cycle.get('score')
            if recovery_score:
                logger.info(f"[WHOOP_CLIENT] ✓ Found recovery data in cycle {i+1}/{len(cycles)}")
                # Return the recovery score data with cycle_id for reference
                recovery_score['cycle_id'] = cycle.get('id')
                recovery_score['created_at'] = cycle.get('created_at')
                recovery_score['updated_at'] = cycle.get('updated_at')
                # Use cycle ID as recovery ID for tracking
                recovery_score['id'] = cycle.get('id')
                return recovery_score

        logger.info(f"[WHOOP_CLIENT] Checked {len(cycles)} cycles, none had recovery data")
        return None

    def get_sleep_with_recovery(self, sleep_id: str) -> Optional[Dict]:
        """
        Get sleep record with associated recovery score.

        Args:
            sleep_id: WHOOP sleep record ID

        Returns:
            dict: Combined sleep and recovery data or None if not found
                {
                    'sleep': {...},
                    'recovery': {...}
                }

        Raises:
            requests.HTTPError: If API call fails
        """
        # Get recent sleep and cycle records
        sleep_data = self.get_sleep_collection(limit=50)
        cycle_data = self.get_cycle_collection(limit=50)

        # Find matching sleep
        sleep = next((s for s in sleep_data.get('records', []) if s['id'] == sleep_id), None)
        if not sleep:
            return None

        # Find matching cycle for this sleep
        # Note: sleep.id can be referenced by cycle data, but we need to check the API docs
        # for the exact relationship. For now, try to get recovery from recent cycles.
        recovery = None
        for cycle in cycle_data.get('records', []):
            cycle_id = cycle.get('id')
            if cycle_id:
                rec = self.get_cycle_recovery(cycle_id)
                if rec:
                    recovery = rec
                    break  # Use the first recovery we find

        return {
            'sleep': sleep,
            'recovery': recovery
        }


class WHOOPClientFactory:
    """Factory for creating WHOOP clients with token refresh."""

    def __init__(self, memory_store, whoop_oauth):
        """
        Initialize factory.

        Args:
            memory_store: MemoryStore instance
            whoop_oauth: WHOOPOAuth class (not instance)
        """
        self.memory = memory_store
        self.oauth = whoop_oauth

    def get_client(self, user_id: int) -> Optional[WHOOPClient]:
        """
        Get WHOOP client for user, refreshing token if needed.

        Args:
            user_id: User ID

        Returns:
            WHOOPClient instance or None if no valid credentials
        """
        creds = self.memory.get_whoop_credentials(user_id)
        if not creds or not creds['is_valid']:
            logger.warning(f"[WHOOP_FACTORY] No valid credentials for user {user_id}")
            return None

        # Check if token is expired
        if creds['expires_at'] < datetime.utcnow():
            logger.info(f"[WHOOP_FACTORY] Token expired for user {user_id}, refreshing...")
            # Refresh token
            try:
                new_token = self.oauth.refresh_access_token(creds['refresh_token'])
                if not new_token:
                    logger.error(f"[WHOOP_FACTORY] Token refresh failed for user {user_id}")
                    self.memory.invalidate_whoop_credentials(user_id, "Token refresh failed")
                    return None

                # Update stored credentials
                self.memory.update_whoop_token(
                    user_id,
                    new_token['access_token'],
                    new_token['expires_at']
                )

                logger.info(f"[WHOOP_FACTORY] Token refreshed successfully for user {user_id}")
                return WHOOPClient(new_token['access_token'])

            except Exception as e:
                logger.error(f"[WHOOP_FACTORY] Token refresh exception for user {user_id}: {e}")
                self.memory.invalidate_whoop_credentials(user_id, str(e))
                return None

        # Token is valid, create client
        return WHOOPClient(creds['access_token'])
