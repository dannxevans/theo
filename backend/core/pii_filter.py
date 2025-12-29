"""
PII Filter Module

Provides regex-based PII redaction for OFFICIAL mode (work mode with PII protection).
Filters personally identifiable information before sending to LLM.

Supported PII types:
- Email addresses
- Phone numbers (US/UK formats)
- Social Security Numbers (SSN)
- Credit card numbers
- Personal names (experimental)
- Street addresses (experimental)
"""

import re
import json
import logging
from typing import Tuple, List, Dict


class PIIFilter:
    """Pre-LLM PII redaction for work mode (OFFICIAL)."""

    # Regex patterns for PII detection
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Phone patterns (US and UK formats)
    PHONE_PATTERNS = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US: 123-456-7890, 123.456.7890, 1234567890
        r'\b\(\d{3}\)\s?\d{3}[-.]?\d{4}\b',  # US: (123) 456-7890
        r'\b\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US international
        r'\b\+44[-.\s]?\d{4}[-.\s]?\d{6}\b',  # UK
        r'\b0\d{4}\s?\d{6}\b',  # UK landline
    ]

    SSN_PATTERN = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'  # SSN: 123-45-6789

    # Credit card patterns (Visa, MC, Amex, Discover)
    CC_PATTERNS = [
        r'\b4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Visa
        r'\b5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # MasterCard
        r'\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b',  # Amex
        r'\b6011[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Discover
    ]

    # Name pattern (experimental - high false positive rate)
    # Matches capitalized words that look like names (2-3 consecutive)
    NAME_PATTERN = r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b'

    # Address pattern (experimental - basic street address detection)
    ADDRESS_PATTERN = r'\b\d+\s+[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b'

    def __init__(self, config: Dict = None):
        """
        Initialize PII filter with configuration.

        Args:
            config: Dictionary with:
                - pii_filtering_enabled (bool)
                - pii_redaction_config (str/dict): JSON config or dict
        """
        self.enabled = False
        self.redact_emails = True
        self.redact_phones = True
        self.redact_ssns = True
        self.redact_credit_cards = True
        self.redact_names = False  # Experimental
        self.redact_addresses = False  # Experimental
        self.redaction_char = "*"

        if config:
            self.enabled = config.get("pii_filtering_enabled", False)

            # Parse redaction config
            redaction_config = config.get("pii_redaction_config")
            if redaction_config:
                if isinstance(redaction_config, str):
                    try:
                        redaction_config = json.loads(redaction_config)
                    except json.JSONDecodeError:
                        logging.warning("[PII] Invalid JSON in pii_redaction_config, using defaults")
                        redaction_config = {}

                if isinstance(redaction_config, dict):
                    self.redact_emails = redaction_config.get("emails", True)
                    self.redact_phones = redaction_config.get("phones", True)
                    self.redact_ssns = redaction_config.get("ssns", True)
                    self.redact_credit_cards = redaction_config.get("creditCards", True)
                    self.redact_names = redaction_config.get("names", False)
                    self.redact_addresses = redaction_config.get("addresses", False)

    def filter_text(self, text: str) -> Tuple[str, List[Dict]]:
        """
        Filter PII from text.

        Args:
            text: Input text

        Returns:
            Tuple of (redacted_text, redaction_log)
            redaction_log is a list of dicts with: {type, original, position}
        """
        if not self.enabled or not text:
            return text, []

        redacted = text
        redactions = []

        # Apply each redaction type
        if self.redact_emails:
            redacted, email_redactions = self._redact_pattern(
                redacted, self.EMAIL_PATTERN, "EMAIL"
            )
            redactions.extend(email_redactions)

        if self.redact_phones:
            for pattern in self.PHONE_PATTERNS:
                redacted, phone_redactions = self._redact_pattern(
                    redacted, pattern, "PHONE"
                )
                redactions.extend(phone_redactions)

        if self.redact_ssns:
            redacted, ssn_redactions = self._redact_pattern(
                redacted, self.SSN_PATTERN, "SSN"
            )
            redactions.extend(ssn_redactions)

        if self.redact_credit_cards:
            for pattern in self.CC_PATTERNS:
                redacted, cc_redactions = self._redact_pattern(
                    redacted, pattern, "CREDIT_CARD"
                )
                redactions.extend(cc_redactions)

        if self.redact_names:
            redacted, name_redactions = self._redact_pattern(
                redacted, self.NAME_PATTERN, "NAME"
            )
            redactions.extend(name_redactions)

        if self.redact_addresses:
            redacted, addr_redactions = self._redact_pattern(
                redacted, self.ADDRESS_PATTERN, "ADDRESS"
            )
            redactions.extend(addr_redactions)

        if redactions:
            logging.info(f"[PII] Redacted {len(redactions)} PII instances: {[r['type'] for r in redactions]}")

        return redacted, redactions

    def _redact_pattern(self, text: str, pattern: str, pii_type: str) -> Tuple[str, List[Dict]]:
        """
        Redact a specific pattern from text.

        Args:
            text: Input text
            pattern: Regex pattern to match
            pii_type: Type of PII (for logging)

        Returns:
            Tuple of (redacted_text, redactions_list)
        """
        redactions = []
        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        # Process matches in reverse order to preserve positions
        for match in reversed(matches):
            original = match.group()
            start, end = match.span()

            # Create redacted replacement
            replacement = f"[REDACTED {pii_type}]"

            # Log redaction
            redactions.insert(0, {
                "type": pii_type,
                "original": original,
                "position": start,
                "length": len(original)
            })

            # Replace in text
            text = text[:start] + replacement + text[end:]

        return text, redactions

    def get_redaction_stats(self, redaction_log: List[Dict]) -> Dict:
        """
        Get statistics about redactions performed.

        Args:
            redaction_log: List of redaction dicts

        Returns:
            Dict with counts by type
        """
        stats = {}
        for redaction in redaction_log:
            pii_type = redaction["type"]
            stats[pii_type] = stats.get(pii_type, 0) + 1
        return stats


def preview_pii_redaction(text: str, config: Dict) -> str:
    """
    Preview PII redaction (for frontend testing).

    Args:
        text: Input text
        config: Redaction config dict

    Returns:
        Redacted text preview
    """
    filter_config = {
        "pii_filtering_enabled": True,
        "pii_redaction_config": config
    }

    pii_filter = PIIFilter(filter_config)
    redacted_text, _ = pii_filter.filter_text(text)
    return redacted_text
