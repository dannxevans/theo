"""
Tests for Work Mode IP Operations.

Tests IP configuration, validation, and access checking.
"""

import pytest
import json


class TestWorkModeIPConfiguration:
    """Tests for IP configuration management."""

    def test_get_ip_config_default(self, memory):
        """Test getting default IP configuration."""
        config = memory.get_work_mode_ip_config()

        assert config is not None
        assert isinstance(config, dict)
        assert "enabled" in config
        assert "allowed_ranges" in config
        assert config["enabled"] == False
        assert isinstance(config["allowed_ranges"], list)
        assert len(config["allowed_ranges"]) == 0

    def test_update_ip_config_enables_feature(self, memory):
        """Test updating IP config to enable restrictions."""
        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.0/24"]
        )

        assert config["enabled"] == True
        assert len(config["allowed_ranges"]) == 1
        assert config["allowed_ranges"][0] == "192.168.1.0/24"

        # Verify persistence
        retrieved_config = memory.get_work_mode_ip_config()
        assert retrieved_config["enabled"] == True
        assert len(retrieved_config["allowed_ranges"]) == 1

    def test_update_ip_config_multiple_ranges(self, memory):
        """Test updating config with multiple CIDR ranges."""
        ranges = [
            "192.168.1.0/24",
            "10.0.0.0/8",
            "203.0.113.42/32"
        ]

        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=ranges
        )

        assert config["enabled"] == True
        assert len(config["allowed_ranges"]) == 3
        assert config["allowed_ranges"] == ranges

    def test_update_ip_config_invalid_cidr_rejected(self, memory):
        """Test that invalid CIDR ranges are rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory.update_work_mode_ip_config(
                enabled=True,
                allowed_ranges=["not-a-valid-cidr"]
            )

        assert "Invalid CIDR notation" in str(exc_info.value)

    def test_update_ip_config_partial_invalid_cidr(self, memory):
        """Test that mixed valid/invalid ranges are rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory.update_work_mode_ip_config(
                enabled=True,
                allowed_ranges=[
                    "192.168.1.0/24",  # Valid
                    "invalid-cidr",    # Invalid
                    "10.0.0.0/8"       # Valid
                ]
            )

        assert "Invalid CIDR notation" in str(exc_info.value)

    def test_update_ip_config_empty_ranges(self, memory):
        """Test updating config with empty ranges list."""
        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=[]
        )

        assert config["enabled"] == True
        assert config["allowed_ranges"] == []

    def test_update_ip_config_disable_with_ranges(self, memory):
        """Test disabling IP restrictions while keeping ranges."""
        # First set it up
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.0/24"]
        )

        # Then disable
        config = memory.update_work_mode_ip_config(
            enabled=False,
            allowed_ranges=["192.168.1.0/24"]
        )

        assert config["enabled"] == False
        assert len(config["allowed_ranges"]) == 1


class TestIPAccessChecking:
    """Tests for IP address access validation."""

    def test_is_ip_allowed_when_disabled(self, memory):
        """Test that all IPs are allowed when feature is disabled."""
        memory.update_work_mode_ip_config(enabled=False, allowed_ranges=[])

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.1.1")

        assert is_allowed == True
        assert reason == "IP restrictions disabled"

    def test_is_ip_allowed_when_enabled_no_ranges(self, memory):
        """Test that all IPs are blocked when enabled with no ranges."""
        memory.update_work_mode_ip_config(enabled=True, allowed_ranges=[])

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.1.1")

        assert is_allowed == False
        assert reason == "No allowed IP ranges configured"

    def test_is_ip_allowed_single_ip_match(self, memory):
        """Test IP checking with single IP CIDR (x.x.x.x/32)."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.100/32"]
        )

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.1.100")

        assert is_allowed == True
        assert "192.168.1.100/32" in reason

    def test_is_ip_allowed_single_ip_no_match(self, memory):
        """Test IP checking with single IP that doesn't match."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.100/32"]
        )

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.1.101")

        assert is_allowed == False
        assert reason == "IP address not in any allowed range"

    def test_is_ip_allowed_subnet_match(self, memory):
        """Test IP checking with subnet CIDR."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.0/24"]
        )

        # Test various IPs in the subnet
        for ip in ["192.168.1.1", "192.168.1.100", "192.168.1.254"]:
            is_allowed, reason = memory.is_ip_allowed_for_work_mode(ip)
            assert is_allowed == True
            assert "192.168.1.0/24" in reason

    def test_is_ip_allowed_subnet_no_match(self, memory):
        """Test IP checking with IP outside subnet."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.0/24"]
        )

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.2.1")

        assert is_allowed == False
        assert reason == "IP address not in any allowed range"

    def test_is_ip_allowed_multiple_ranges(self, memory):
        """Test IP checking with multiple CIDR ranges."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=[
                "192.168.1.0/24",
                "10.0.0.0/8",
                "203.0.113.42/32"
            ]
        )

        # Test IP in first range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("192.168.1.50")
        assert is_allowed == True

        # Test IP in second range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("10.5.10.100")
        assert is_allowed == True

        # Test exact IP match
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("203.0.113.42")
        assert is_allowed == True

        # Test IP not in any range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("8.8.8.8")
        assert is_allowed == False

    def test_is_ip_allowed_invalid_ip_format(self, memory):
        """Test IP checking with invalid IP address format."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.0/24"]
        )

        is_allowed, reason = memory.is_ip_allowed_for_work_mode("not-an-ip")

        assert is_allowed == False
        assert "Invalid IP address format" in reason

    def test_is_ip_allowed_ipv6_support(self, memory):
        """Test IP checking with IPv6 addresses."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["2001:db8::/32"]
        )

        # Test IPv6 in range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("2001:db8::1")
        assert is_allowed == True

        # Test IPv6 not in range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("2001:db9::1")
        assert is_allowed == False

    def test_is_ip_allowed_large_network(self, memory):
        """Test IP checking with large network (class A)."""
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["10.0.0.0/8"]
        )

        # Test IPs across the range
        test_ips = [
            "10.0.0.1",
            "10.127.255.254",
            "10.255.255.255"
        ]

        for ip in test_ips:
            is_allowed, reason = memory.is_ip_allowed_for_work_mode(ip)
            assert is_allowed == True

        # Test IP outside range
        is_allowed, reason = memory.is_ip_allowed_for_work_mode("11.0.0.1")
        assert is_allowed == False


class TestCIDRValidation:
    """Tests for CIDR notation validation."""

    def test_validate_cidr_valid_ipv4_single(self, memory):
        """Test validation of single IPv4 address CIDR."""
        # Should not raise
        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=["192.168.1.100/32"]
        )
        assert len(config["allowed_ranges"]) == 1

    def test_validate_cidr_valid_ipv4_subnet(self, memory):
        """Test validation of IPv4 subnet CIDR."""
        # Various valid subnet masks
        valid_ranges = [
            "192.168.1.0/24",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "203.0.113.0/25"
        ]

        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=valid_ranges
        )
        assert len(config["allowed_ranges"]) == len(valid_ranges)

    def test_validate_cidr_valid_ipv6(self, memory):
        """Test validation of IPv6 CIDR."""
        valid_ranges = [
            "2001:db8::/32",
            "fe80::/10",
            "::1/128"
        ]

        config = memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=valid_ranges
        )
        assert len(config["allowed_ranges"]) == len(valid_ranges)

    def test_validate_cidr_invalid_format(self, memory):
        """Test validation rejects invalid CIDR formats."""
        invalid_ranges = [
            "not-a-cidr",
            "192.168.1",
            "192.168.1.1.1",
            "192.168.1.1/",
            "192.168.1.1/33",  # Invalid prefix length for IPv4
            "192.168.1.0/99"   # Invalid prefix length
        ]

        for invalid_range in invalid_ranges:
            with pytest.raises(ValueError) as exc_info:
                memory.update_work_mode_ip_config(
                    enabled=True,
                    allowed_ranges=[invalid_range]
                )
            assert "Invalid CIDR notation" in str(exc_info.value)

    def test_validate_cidr_preserves_valid_ranges(self, memory):
        """Test that existing valid ranges are preserved after validation."""
        initial_ranges = ["192.168.1.0/24", "10.0.0.0/8"]

        # Set initial ranges
        memory.update_work_mode_ip_config(
            enabled=True,
            allowed_ranges=initial_ranges
        )

        # Try to update with invalid range (should fail)
        with pytest.raises(ValueError):
            memory.update_work_mode_ip_config(
                enabled=True,
                allowed_ranges=["invalid-cidr"]
            )

        # Verify original ranges are still intact
        config = memory.get_work_mode_ip_config()
        assert config["allowed_ranges"] == initial_ranges
