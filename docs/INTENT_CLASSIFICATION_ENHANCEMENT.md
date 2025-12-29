# Intent Classification Enhancement

**Date**: December 29, 2025
**Issue**: Calendar actions were being triggered inappropriately in Code Development context
**Solution**: Hybrid LLM-assisted intent classification with mode awareness

---

## Problem

When working in **Work Mode > Code Development** and asking technical questions about ServiceNow automation, the system was incorrectly routing to calendar booking because:

1. Message contained the word "schedule" (in ServiceNow context)
2. Intent classifier matched on single keywords without context
3. No awareness of work mode or sub-tab

**Example**:
```
User (in Code Development): "I want to replace our Delivery Managers manual
jobs with automation using ServiceNow. Here is what they do: Identify the
release they want to plan for, using rm_release_scrum where the state is
planning (state = 1)..."

System (incorrectly): Created calendar event "ServiceNow Release Planning
Automation Discussion"
```

---

## Solution: Hybrid Intent Classification

Implemented a **3-tier approach** that's both accurate and cost-conscious:

### Tier 1: Context-Based Filtering (Free, Fast)
- Checks work mode (work/personal)
- Checks sub-tab (code/email/conversation)
- Checks message length and complexity
- Returns high-confidence intent if strong context match

**Logic**:
- If in **Code Development** + multiple technical keywords → `coding` intent (95% confidence)
- If in **Work Mode > Email** + no explicit calendar phrases → `general` intent (95% confidence)
  - Work mode Email tab is for LLM-assisted email composition, NOT M365 actions
  - Personal mode Email tab still triggers `compose_email` for M365 actions

### Tier 2: Keyword Matching (Free, Fast)
- Enhanced keyword matching with mode-aware confidence scoring
- Strong calendar signals (regex patterns):
  - `add X to my calendar`
  - `put X on my calendar`
  - `book me` / `schedule me`
  - `create appointment`
- Weak calendar signals (require context):
  - `schedule` / `book` / `arrange` (only match if calendar context present)

**Mode-Aware Weighting**:
- Weak signal + Code Development context → Low confidence (30%)
- Weak signal + Personal mode → Medium confidence (60%)
- Strong signal → High confidence (90%) regardless of mode

### Tier 3: LLM Clarification (Cheap, Only When Ambiguous)
- **Only triggered if confidence < 80%**
- Uses **Haiku** (cheapest Claude model)
- Simple yes/no prompt (~$0.001 per call)
- Designed to run rarely (most cases resolved in Tier 1/2)

**Example LLM Prompt**:
```
You are helping classify user intent.

User message: "Can you help me schedule the release planning?"

Context: User is in WORK mode, specifically in the 'code' tab.

Question: Is this message asking to CREATE A CALENDAR EVENT/APPOINTMENT?

Answer ONLY with one of these exact words:
- "book_appointment" if YES
- "coding" if this is a technical/programming question
- "compose_email" if about writing/sending an email
- "general" if none of the above
```

---

## Implementation

### New File: `backend/core/intent_classifier.py`
Contains `IntentClassifier` class with:
- `classify()` - Main entry point
- `_check_context_signals()` - Tier 1: Context checking
- `_keyword_match()` - Tier 2: Enhanced keyword matching
- `_llm_clarify()` - Tier 3: LLM disambiguation

### Updated Files

**`backend/core/router.py`**:
- Added import: `from core.intent_classifier import classify_intent_enhanced`
- Updated `route_request()` to pass mode and subtab to classifier

**`backend/routes/message_routes.py`**:
- Added `router_context["mode"]` and `router_context["subtab"]`
- Extracts work mode and sub-tab from request params

---

## Test Results

| Scenario | Mode | Subtab | Expected | Result | ✓ |
|----------|------|--------|----------|--------|---|
| ServiceNow automation question | work | code | coding | coding | ✅ |
| "Add lunch to my calendar" | work | code | book_appointment | book_appointment | ✅ |
| "Put meeting on calendar" | work | code | book_appointment | book_appointment | ✅ |
| "schedule release planning" | work | code | general | general | ✅ |
| "schedule release planning" | personal | - | general | general | ✅ |

---

## Benefits

### 1. Context-Aware Classification ✅
- Understands work mode vs personal mode
- Understands sub-tab context (code/email/conversation)
- Technical questions stay in coding context

### 2. Cost-Conscious ✅
- **Tier 1 & 2**: Free (keyword + context)
- **Tier 3**: Rare (~5% of cases)
- **Cost**: ~$0.001 per LLM call when needed
- **Estimated monthly cost**: $1-5 for typical usage

### 3. High Accuracy ✅
- Strong signals (e.g., "add to calendar") always detected
- Weak signals (e.g., "schedule") context-dependent
- Technical discussions don't trigger calendar

### 4. Improved UX ✅
- Appropriate responses in each mode
- Less false calendar triggers
- Better intent matching overall

---

## Future Enhancements

### 1. Learning from Corrections
Track when users reject confirmations:
```python
if user_rejected_calendar_action and intent_was_book_appointment:
    # Learn that this context shouldn't trigger calendar
    update_intent_confidence_weights()
```

### 2. User-Specific Intent Patterns
```python
# Track per-user patterns
if user.frequently_uses_schedule_in_technical_context:
    reduce_calendar_match_confidence()
```

### 3. Multi-Intent Detection
```python
# Detect when message has multiple intents
"Write an email to John AND add meeting to my calendar"
→ ["compose_email", "book_appointment"]
```

### 4. Confidence Threshold Tuning
```python
# Make LLM threshold configurable
if confidence < user_settings.llm_threshold:
    use_llm_clarification()
```

---

## Configuration

### Environment Variables
None required - works out of the box.

### Mode Configuration
Set via Work Mode settings in UI:
- Work Mode > Code Development
- Work Mode > Email Rewrites
- Work Mode > Conversation (OFFICIAL)

### Cost Control
LLM clarification is opt-in via provider registry availability:
```python
# To disable LLM clarification, don't pass provider_registry
intent = classify_intent_enhanced(
    text=text,
    mode=mode,
    subtab=subtab,
    provider_registry=None  # Disables Tier 3
)
```

---

## Monitoring

### Logging
Intent classification logs include:
```
[INTENT] Context check → coding (confidence: 0.95)
[INTENT] Keyword match → book_appointment (confidence: 0.60)
[INTENT] Low confidence (0.60), using LLM to clarify...
[INTENT] LLM override → coding (confidence: 0.85)
[INTENT] Final classification: coding (confidence: 0.85)
```

### Metrics to Track
- Classification confidence scores
- LLM usage rate (should be < 10%)
- False positive rate (calendar triggers)
- User rejections of confirmations

---

## Code Examples

### Basic Usage
```python
from core.intent_classifier import classify_intent_enhanced

intent = classify_intent_enhanced(
    text="Add lunch with mom to my calendar",
    mode="work",
    subtab="code"
)
# Returns: "book_appointment"
```

### With Provider Registry (enables LLM)
```python
intent = classify_intent_enhanced(
    text="Can you help me schedule the release?",
    mode="work",
    subtab="code",
    provider_registry=provider_registry  # Enables Tier 3
)
# Context + keywords = low confidence
# LLM clarifies → "coding"
```

### Getting Confidence Score
```python
from core.intent_classifier import IntentClassifier

classifier = IntentClassifier(memory, provider_registry)
intent, confidence = classifier.classify(
    text="Schedule the deployment",
    mode="work",
    subtab="code"
)

if confidence < 0.70:
    # Show user a clarification UI
    ask_user_to_confirm_intent()
```

---

## Rollback

If issues arise, revert to old classification:

1. **Remove import** in `backend/core/router.py`:
   ```python
   # Remove: from core.intent_classifier import classify_intent_enhanced
   ```

2. **Restore old call**:
   ```python
   # Replace
   intent = classify_intent_enhanced(...)

   # With
   intent = classify_intent(text, memory, user_id=context.get("user_id"))
   ```

3. **Restart backend**:
   ```bash
   pkill -f "python.*app.py"
   python backend/app.py
   ```

---

## Conclusion

The enhanced intent classification provides:
- ✅ Context-aware routing
- ✅ Cost-effective LLM assistance
- ✅ Better user experience in work modes
- ✅ Reduced false calendar triggers

This solves the immediate issue while providing a foundation for future intent classification improvements.

---

## Mode-Based Action Restrictions

**Date**: December 29, 2025
**Enhancement**: Personal actions (M365 calendar/email) are now blocked in work mode

### Rationale
Work mode is for professional context with PII protection. Personal M365 actions (calendar events, email sending) should only be available in personal mode.

### Implementation
In `backend/core/router.py`, personal actions are blocked when in work mode:
```python
PERSONAL_ACTIONS = ["read_calendar", "book_appointment", "update_appointment",
                   "cancel_appointment", "read_email", "compose_email"]

if current_mode == "work" and intent in PERSONAL_ACTIONS:
    return {
        "text": "Calendar and email actions are not available in Work mode. "
                "These are personal actions. Please switch to Personal mode.",
        "provider": "error",
        "fallback_reason": "personal_action_in_work_mode",
    }
```

### Behavior
| Mode | Tab | User Action | Intent | Result |
|------|-----|-------------|--------|--------|
| Work | Email | Paste email to rewrite | `general` | ✅ LLM helps rewrite |
| Work | Code | "Add to calendar" | `book_appointment` | ❌ Blocked with message |
| Work | Any | "Send email to..." | `compose_email` | ❌ Blocked with message |
| Personal | - | "Add to calendar" | `book_appointment` | ✅ M365 action triggered |
| Personal | - | "Send email to..." | `compose_email` | ✅ M365 action triggered |

### Key Points
- **Work Mode + Email Tab**: LLM assistance for email composition (not M365 actions)
- **Personal Mode**: M365 calendar and email actions available
- **Work Mode Protection**: Personal actions blocked to maintain professional context separation

---

## Related Issues

- Original issue: Calendar triggered inappropriately in Code Development mode
- Enhancement: Personal actions blocked in work mode (December 29, 2025)
- Related: #67 (Work Mode PII - Names too aggressive)
- Related: #65 & #66 (Backend Cleanup - Completed)
