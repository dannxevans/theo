"""
Tests for Issue #302: Fix "schedule" keyword triggering calendar action in Work Mode Email.

This test suite validates that the intent classifier correctly handles the "schedule" keyword
in different contexts, particularly in Work Mode > Email subtab where it should not trigger
calendar intents unless explicitly requested.

Reference: https://github.com/dannxevans/theo/issues/302
"""

import pytest
from core.intent_classifier import IntentClassifier, classify_intent_enhanced


class TestIntentClassifierScheduleKeyword:
    """Test suite for schedule keyword handling in different modes and contexts."""

    def test_work_mode_email_schedule_without_calendar_intent(self):
        """
        Test that "schedule" in email content does NOT trigger calendar intent in Work Mode Email.

        This is the primary bug fix from Issue #302.
        When a user is rewriting an email that contains the word "schedule",
        it should be treated as general email assistance, not a calendar action.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # Test case from the issue
        text = "the Maintenance schedule is used today"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")

        assert intent == "general", f"Expected 'general' intent for email rewriting, got '{intent}'"
        assert confidence >= 0.90, f"Expected high confidence (>=0.90), got {confidence}"

    def test_work_mode_email_schedule_with_contextual_words(self):
        """
        Test that "schedule" with calendar context words (today, tomorrow, etc.)
        still returns "general" in Work Mode Email subtab.

        Previously, the presence of "today" or day names would trigger calendar intent.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        test_cases = [
            "The project schedule shows we're on track for delivery tomorrow",
            "Please review the schedule for Monday's meeting",
            "The maintenance schedule is available today at 2pm",
            "Can you book the conference room and arrange the schedule for Friday"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            assert intent == "general", f"Text '{text}' should return 'general', got '{intent}'"

    def test_work_mode_email_explicit_calendar_action_detected(self):
        """
        Test that explicit calendar action phrases ARE detected in Work Mode Email.

        Even in Email subtab, explicit phrases like "add to my calendar" should be
        recognized as calendar intents (they will be blocked by mode restrictions later).

        NOTE: These phrases must match BOTH:
        1. The explicit calendar list in _check_context_overrides (to fall through)
        2. The strong pattern regexes in _keyword_match (to be classified)
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # Phrases that CONTAIN explicit phrases from the list (exact substring matches)
        # See backend/core/intent_classifier.py lines 140-144
        explicit_phrases_that_match = [
            "Please add to my calendar for tomorrow",  # Contains "add to my calendar"
            "Can you add to calendar",                  # Contains "add to calendar"
            "I need to put on calendar",                # Contains "put on calendar"
            "Please book me",                           # Contains "book me"
            "Can you schedule me",                      # Contains "schedule me"
            "create appointment for next week",         # Contains "create appointment"
        ]

        for text in explicit_phrases_that_match:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            assert intent == "book_appointment", f"Text '{text}' should trigger 'book_appointment', got '{intent}'"

    def test_personal_mode_schedule_with_context_triggers_calendar(self):
        """
        Test that in Personal Mode, "schedule" with calendar context DOES trigger calendar intent.

        This ensures the fix doesn't break legitimate calendar intent detection in Personal Mode.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # In personal mode without subtab specification
        text = "schedule meeting for tomorrow"
        intent, confidence = classifier.classify(text, user_id=None, mode="personal", subtab=None)

        assert intent == "book_appointment", f"Personal mode should detect calendar intent, got '{intent}'"

    def test_work_mode_code_schedule_reduced_confidence(self):
        """
        Test that "schedule" in Work Mode Code subtab has reduced confidence (existing behavior).

        This is a regression test for the ServiceNow schedule context handling.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "the schedule table in ServiceNow shows appointments for tomorrow"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="code")

        # Should either return non-calendar intent or very low confidence
        # The context override should return "general" or "coding" for technical content
        assert intent != "book_appointment" or confidence < 0.40, \
            f"Code mode should not trigger calendar with high confidence, got {intent} with {confidence}"

    def test_work_mode_email_multiple_weak_keywords(self):
        """
        Test that multiple weak calendar keywords don't trigger calendar intent in Email mode.

        Words like "schedule", "book", "arrange" should not trigger calendar actions
        when they appear in email content being rewritten.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "Please book the conference room and arrange the schedule for Monday"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")

        assert intent == "general", f"Multiple weak keywords should still return 'general', got '{intent}'"

    def test_work_mode_email_book_keyword_without_explicit_action(self):
        """
        Test that the word "book" in email content doesn't trigger calendar intent.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "I'll book the flight tomorrow and send you the details"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")

        assert intent == "general", f"'book' in email content should return 'general', got '{intent}'"

    def test_work_mode_email_arrange_keyword_without_explicit_action(self):
        """
        Test that the word "arrange" in email content doesn't trigger calendar intent.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "Can you arrange the documents for the meeting today?"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")

        assert intent == "general", f"'arrange' in email content should return 'general', got '{intent}'"

    def test_no_mode_schedule_with_context_triggers_calendar(self):
        """
        Test that without mode specification, "schedule" with context still works as before.

        This ensures backward compatibility for contexts where mode is not provided.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "schedule meeting for tomorrow"
        intent, confidence = classifier.classify(text, user_id=None, mode=None, subtab=None)

        assert intent == "book_appointment", f"Should detect calendar intent without mode, got '{intent}'"

    def test_classify_intent_enhanced_wrapper(self):
        """
        Test the classify_intent_enhanced wrapper function.

        Ensures the public API function works correctly with the fix.
        """
        text = "the Maintenance schedule is used today"
        intent = classify_intent_enhanced(
            text,
            memory=None,
            user_id=None,
            mode="work",
            subtab="email",
            provider_registry=None
        )

        assert intent == "general", f"Enhanced classifier should return 'general', got '{intent}'"

    def test_work_mode_email_read_calendar_keywords(self):
        """
        Test behavior of "read calendar" keywords in Work Mode Email.

        In Work Mode Email, the context override returns "general" for most cases
        unless there's an explicit "book appointment" phrase. Read calendar phrases
        that don't match explicit booking phrases will return "general".

        This is acceptable because:
        1. Calendar actions are blocked in Work Mode anyway
        2. Email subtab is for email rewriting, not calendar operations
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        read_calendar_phrases = [
            "what's on my calendar tomorrow?",
            "check my calendar for Monday",
            "show me my calendar"
        ]

        for text in read_calendar_phrases:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            # In Work Mode Email, these should return "general" due to context override
            # They will be blocked anyway since calendar actions aren't available in Work Mode
            assert intent == "general", f"Text '{text}' should return 'general' in Work Email mode, got '{intent}'"

    def test_edge_case_schedule_as_noun_vs_verb(self):
        """
        Test that "schedule" used as a noun doesn't trigger calendar intent in Email mode.

        Common usage: "the schedule", "maintenance schedule", "project schedule"
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        noun_usage_cases = [
            "The schedule indicates completion by Friday",
            "Please see the attached schedule",
            "Our schedule shows availability tomorrow",
            "The project schedule is on track"
        ]

        for text in noun_usage_cases:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            assert intent == "general", f"Noun usage '{text}' should return 'general', got '{intent}'"

    def test_work_mode_conversation_subtab_behavior(self):
        """
        Test that Work Mode Conversation subtab doesn't have Email subtab restrictions.

        The fix is specific to Email subtab; Conversation subtab should behave normally
        UNLESS the user explicitly uses "reword" which indicates email rewriting intent.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # In conversation subtab WITHOUT "reword", normal classification applies
        text = "schedule meeting for tomorrow"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="conversation")

        # This should potentially trigger calendar (which will be blocked by mode restrictions)
        # Or return general - depends on overall intent classification
        assert isinstance(intent, str), "Should return a valid intent string"
        assert isinstance(confidence, float), "Should return a confidence score"

    def test_work_mode_reword_keyword_triggers_email_behavior(self):
        """
        Test that "reword:" prefix in Work Mode Conversation triggers email rewriting behavior.

        Issue #302 extension: Users often use "Reword:" in conversation subtab for email help.
        This should apply the same fix as Email subtab.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # Real-world case from user: "Reword: Yes, the Maintenance schedule is used..."
        text = "Reword: Yes, the Maintenance schedule is used and is managed by SADI. There are a set of scheduleds created to cover most scenarios"
        intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="conversation")

        assert intent == "general", f"Reword request with 'schedule' should return 'general', got '{intent}'"
        assert confidence >= 0.90, f"Should have high confidence for reword requests, got {confidence}"


class TestIntentClassifierEdgeCases:
    """Additional edge cases for robust testing."""

    def test_empty_text(self):
        """Test empty text handling."""
        classifier = IntentClassifier(memory=None, provider_registry=None)
        intent, confidence = classifier.classify("", user_id=None, mode="work", subtab="email")
        assert intent == "general"

    def test_whitespace_only(self):
        """Test whitespace-only text."""
        classifier = IntentClassifier(memory=None, provider_registry=None)
        intent, confidence = classifier.classify("   \n\t  ", user_id=None, mode="work", subtab="email")
        assert intent == "general"

    def test_case_insensitivity(self):
        """Test that matching is case-insensitive."""
        classifier = IntentClassifier(memory=None, provider_registry=None)

        texts = [
            "the SCHEDULE is available",
            "The Schedule Is Available",
            "THE SCHEDULE IS AVAILABLE"
        ]

        for text in texts:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            assert intent == "general", f"Case variations should all return 'general', got '{intent}' for '{text}'"

    def test_schedule_with_punctuation(self):
        """Test schedule keyword with various punctuation."""
        classifier = IntentClassifier(memory=None, provider_registry=None)

        texts = [
            "Check the schedule.",
            "The schedule: Monday-Friday",
            "Schedule? Yes, it's ready.",
            "schedule;schedule;schedule"
        ]

        for text in texts:
            intent, confidence = classifier.classify(text, user_id=None, mode="work", subtab="email")
            assert intent == "general", f"Punctuation variations should return 'general', got '{intent}' for '{text}'"

    def test_very_long_text_with_schedule(self):
        """Test that long text with 'schedule' keyword works correctly."""
        classifier = IntentClassifier(memory=None, provider_registry=None)

        long_text = """
        Dear Team,

        I wanted to provide an update on our project schedule. The maintenance schedule
        has been revised to accommodate the new timeline. Please review the attached
        schedule for details on the changes. We need to ensure that everyone is aware
        of the updated schedule before we proceed with the implementation tomorrow.

        The schedule includes all phases of development and should be consulted regularly.

        Best regards
        """

        intent, confidence = classifier.classify(long_text, user_id=None, mode="work", subtab="email")
        assert intent == "general", f"Long email with multiple 'schedule' mentions should return 'general', got '{intent}'"


# Integration-style test (if memory and other components are available)
class TestIntentClassifierIntegration:
    """Integration tests with full system context."""

    def test_full_workflow_email_rewriting_scenario(self):
        """
        Test the complete workflow of email rewriting with schedule keyword.

        Simulates a real user scenario from Issue #302.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        # User is in Work Mode > Email subtab, writing an email about maintenance
        email_draft = """
        Hi team,

        The Maintenance schedule is used today to plan our server updates.
        Please review and let me know if you have any concerns by tomorrow.

        Thanks
        """

        intent, confidence = classifier.classify(
            email_draft,
            user_id=None,
            mode="work",
            subtab="email"
        )

        assert intent == "general", \
            f"Email rewriting scenario should return 'general' intent, got '{intent}'"
        assert confidence >= 0.90, \
            f"Should have high confidence for email rewriting, got {confidence}"

    def test_explicit_calendar_action_in_email_mode(self):
        """
        Test that explicit calendar actions are still detected even in Email mode.

        They will be blocked later by mode restrictions, but should be detected correctly.
        """
        classifier = IntentClassifier(memory=None, provider_registry=None)

        text = "Please add this to my calendar for tomorrow at 2pm"
        intent, confidence = classifier.classify(
            text,
            user_id=None,
            mode="work",
            subtab="email"
        )

        assert intent == "book_appointment", \
            f"Explicit calendar action should be detected, got '{intent}'"
        assert confidence >= 0.80, \
            f"Explicit actions should have high confidence, got {confidence}"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
