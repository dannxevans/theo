"""
Work Mode IP operations module.

Handles:
- IP restriction configuration for Work Mode
- IP address validation against allowed CIDR ranges
- CIDR notation validation
"""

import json
import ipaddress
from datetime import datetime
from sqlalchemy import select, update

from .base import BaseMemoryOperations


class WorkModeIPOperations(BaseMemoryOperations):
    """Operations for managing Work Mode IP restrictions."""

    def get_ip_config(self):
        """
        Get IP restriction configuration.

        Returns:
            Dictionary with 'enabled' (bool) and 'allowed_ranges' (list[str])
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.work_mode_ip_config)
            ).fetchone()

            if row:
                config = dict(row._mapping)
                # Parse JSON allowed_ranges
                if config.get('allowed_ranges'):
                    try:
                        config['allowed_ranges'] = json.loads(config['allowed_ranges'])
                    except (json.JSONDecodeError, TypeError):
                        config['allowed_ranges'] = []
                else:
                    config['allowed_ranges'] = []
                return config

            # Default config if not found
            return {
                'enabled': False,
                'allowed_ranges': []
            }

    def update_ip_config(self, enabled, allowed_ranges):
        """
        Update IP restriction configuration.

        Args:
            enabled: Boolean to enable/disable IP restrictions
            allowed_ranges: List of CIDR notation strings

        Returns:
            Updated configuration dictionary

        Raises:
            ValueError: If any CIDR range is invalid
        """
        # Validate all CIDR ranges
        for cidr in allowed_ranges:
            if not self._validate_cidr_range(cidr):
                raise ValueError(f"Invalid CIDR notation: {cidr}")

        with self._get_connection() as conn:
            # Convert list to JSON string
            allowed_ranges_json = json.dumps(allowed_ranges)

            # Update or insert
            existing = conn.execute(
                select(self.work_mode_ip_config)
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.work_mode_ip_config)
                    .values(
                        enabled=enabled,
                        allowed_ranges=allowed_ranges_json,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Shouldn't happen due to migration, but handle it
                from sqlalchemy import insert
                conn.execute(
                    insert(self.work_mode_ip_config).values(
                        enabled=enabled,
                        allowed_ranges=allowed_ranges_json
                    )
                )

        # Return updated config
        return {
            'enabled': enabled,
            'allowed_ranges': allowed_ranges
        }

    def is_ip_allowed(self, ip_address):
        """
        Check if an IP address is allowed for Work Mode access.

        Args:
            ip_address: IP address string (IPv4 or IPv6)

        Returns:
            Tuple of (is_allowed: bool, reason: str)
        """
        config = self.get_ip_config()

        # If disabled, all IPs are allowed
        if not config['enabled']:
            return (True, "IP restrictions disabled")

        # If enabled but no ranges configured, block all
        if not config['allowed_ranges']:
            return (False, "No allowed IP ranges configured")

        # Validate IP address format
        try:
            ip = ipaddress.ip_address(ip_address)
        except ValueError:
            return (False, f"Invalid IP address format: {ip_address}")

        # Check if IP is in any allowed range
        for cidr_range in config['allowed_ranges']:
            try:
                network = ipaddress.ip_network(cidr_range, strict=False)
                if ip in network:
                    return (True, f"IP matches allowed range: {cidr_range}")
            except ValueError:
                # Skip invalid CIDR ranges (shouldn't happen due to validation on save)
                continue

        # IP not in any allowed range
        return (False, "IP address not in any allowed range")

    @staticmethod
    def _validate_cidr_range(cidr_string):
        """
        Validate CIDR notation string.

        Args:
            cidr_string: CIDR notation (e.g., "192.168.1.0/24")

        Returns:
            Boolean indicating if valid
        """
        try:
            ipaddress.ip_network(cidr_string, strict=False)
            return True
        except ValueError:
            return False

    @staticmethod
    def ip_in_range(ip_address, cidr_range):
        """
        Check if an IP address falls within a CIDR range.

        Args:
            ip_address: IP address string
            cidr_range: CIDR notation string

        Returns:
            Boolean indicating if IP is in range

        Raises:
            ValueError: If IP address or CIDR range is invalid
        """
        ip = ipaddress.ip_address(ip_address)
        network = ipaddress.ip_network(cidr_range, strict=False)
        return ip in network
