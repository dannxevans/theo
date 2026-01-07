"""
Tests for search intent classification.

Tests search keyword detection and confidence scoring.
"""

import pytest
from core.intent_classifier import IntentClassifier


class TestSearchIntentClassification:
    """Test search intent keyword matching."""

    def test_explicit_search_for(self):
        """Test 'search for' keyword triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("search for the latest AI news")

        assert intent == "search"
        assert confidence == 0.90

    def test_explicit_look_up(self):
        """Test 'look up' keyword triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("look up quantum computing")

        assert intent == "search"
        assert confidence == 0.90

    def test_find_information_about(self):
        """Test 'find information about' triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("find information about climate change")

        assert intent == "search"
        assert confidence == 0.90

    def test_latest_news_about(self):
        """Test 'latest news about' triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("latest news about SpaceX")

        assert intent == "search"
        assert confidence == 0.90

    def test_current_information_about(self):
        """Test 'current information about' triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("current information about Bitcoin prices")

        assert intent == "search"
        assert confidence == 0.90

    def test_real_time_information(self):
        """Test 'real-time information' triggers search intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("real-time information about stock market")

        assert intent == "search"
        assert confidence == 0.90


class TestSearchQuestionPatterns:
    """Test search intent from question patterns."""

    def test_what_is_question_with_recency(self):
        """Test 'what is' question with recency indicator."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what is the latest news about AI")

        assert intent == "search"
        # "latest news about" is a strong search keyword (0.90), not question pattern (0.85)
        assert confidence == 0.90

    def test_who_is_question_with_current(self):
        """Test 'who is' question with current indicator."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("who is the current president of France")

        assert intent == "search"
        assert confidence == 0.85

    def test_where_is_question_with_now(self):
        """Test 'where is' question with now indicator."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("where is the best place to visit now")

        assert intent == "search"
        assert confidence == 0.85

    def test_when_did_question(self):
        """Test 'when did' question with recency."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("when did the recent earthquake happen")

        assert intent == "search"
        assert confidence == 0.85

    def test_how_many_question_with_today(self):
        """Test 'how many' question with today."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("how many people are there today at the event")

        assert intent == "search"
        assert confidence == 0.85

    def test_what_is_capital_question(self):
        """Test factual 'what is' question about capital."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what is the capital of Germany")

        assert intent == "search"
        assert confidence == 0.80

    def test_who_is_ceo_question(self):
        """Test factual 'who is' question about CEO."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("who is the CEO of Tesla")

        assert intent == "search"
        assert confidence == 0.80

    def test_where_is_headquartered_question(self):
        """Test factual 'where is' question about headquarters."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("where is Google headquartered")

        assert intent == "search"
        assert confidence == 0.80


class TestSearchVsGeneralIntent:
    """Test distinguishing search from general conversation."""

    def test_general_conversation_not_search(self):
        """Test general greeting is not classified as search."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("hello, how are you?")

        assert intent == "general"
        assert confidence == 0.50

    def test_coding_question_not_search(self):
        """Test coding question is not classified as search."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("how do I write a function in Python?")

        assert intent == "general"
        # Confidence may vary, just ensure it's not search

    def test_opinion_question_not_search(self):
        """Test opinion question is not classified as search."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what do you think about climate change?")

        # Should not be search - opinions are general conversation
        assert intent != "search"

    def test_hypothetical_question_not_search(self):
        """Test hypothetical question is not classified as search."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what would happen if the sun disappeared?")

        # Hypothetical questions don't require web search
        assert intent != "search"


class TestSearchWithContext:
    """Test search intent with various context clues."""

    def test_search_with_year_indicator(self):
        """Test search with specific year."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what happened in AI research in 2026")

        assert intent == "search"
        assert confidence >= 0.80

    def test_search_with_this_week(self):
        """Test search with 'this week' indicator."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what are the latest developments this week")

        assert intent == "search"
        assert confidence >= 0.80

    def test_search_with_this_month(self):
        """Test search with 'this month' indicator."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("what are the recent news this month about tech")

        assert intent == "search"
        assert confidence >= 0.80


class TestSearchEdgeCases:
    """Test edge cases for search intent."""

    def test_empty_message(self):
        """Test empty message doesn't trigger search."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("")

        assert intent == "general"
        assert confidence == 1.0

    def test_search_case_insensitive(self):
        """Test search keywords are case insensitive."""
        classifier = IntentClassifier()

        intent1, conf1 = classifier.classify("SEARCH FOR latest news")
        intent2, conf2 = classifier.classify("Search For latest news")
        intent3, conf3 = classifier.classify("search for latest news")

        assert intent1 == "search"
        assert intent2 == "search"
        assert intent3 == "search"

    def test_search_with_extra_whitespace(self):
        """Test search keywords work with leading/trailing whitespace."""
        classifier = IntentClassifier()
        # Note: Extra whitespace BETWEEN words breaks the keyword match
        # This tests that leading/trailing whitespace is handled
        intent, confidence = classifier.classify("  search for AI news  ")

        assert intent == "search"
        assert confidence == 0.90


class TestSearchPriority:
    """Test search intent priority relative to other intents."""

    def test_search_overrides_general(self):
        """Test explicit search overrides general intent."""
        classifier = IntentClassifier()
        intent, confidence = classifier.classify("search for information about Python programming")

        # Even though "Python programming" might suggest coding,
        # explicit "search for" should take precedence
        assert intent == "search"
        assert confidence >= 0.80

    def test_action_keywords_not_confused_with_search(self):
        """Test action intents like calendar aren't confused with search."""
        classifier = IntentClassifier()

        # Calendar action
        intent1, _ = classifier.classify("add to my calendar")
        assert intent1 != "search"

        # Email action
        intent2, _ = classifier.classify("send email to John")
        assert intent2 != "search"

    def test_which_is_in_casual_conversation_not_search(self):
        """Test 'which is' in casual conversation doesn't trigger search."""
        classifier = IntentClassifier()

        # False positive case from issue: "which is good" in casual context
        intent1, confidence1 = classifier.classify(
            "Snacks will be sweets and no ad-breaks which is good BBC doesnt have them "
            "like other commercial channels which is good. I am going to go and have a "
            "shower now as I have the stench of the day on me from being in the office."
        )
        assert intent1 != "search", f"Should not trigger search, got {intent1} with confidence {confidence1}"

        # Other casual uses of "which is"
        intent2, _ = classifier.classify("That's the option which is better for me")
        assert intent2 != "search"

        intent3, _ = classifier.classify("The movie which is playing tonight sounds fun")
        assert intent3 != "search"

        # But actual questions at sentence start should still work
        intent4, confidence4 = classifier.classify("What is the capital of France?")
        assert intent4 == "search"
        assert confidence4 >= 0.70

        # But explicit search should work
        intent3, _ = classifier.classify("search for calendar apps")
        assert intent3 == "search"
