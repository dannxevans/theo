"""
Email action handlers.

Provides handlers for email-related actions:
- Reading emails
- Composing emails
- Replying to emails
- Sending emails
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import logging
import re

from .base_handler import BaseActionHandler


class EmailHandlers(BaseActionHandler):
    """Handlers for email-related actions."""

    def handle_read_email(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle email read operations.

        Examples:
        - "Show me my unread emails"
        - "unread email summary"
        - "check my inbox"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with email operation result
        """
        # Get provider
        provider_result = self._get_provider("read_email", user_id)
        if not provider_result:
            return self._format_no_provider_response("read_email", "read_email", "email")

        provider_id, provider = provider_result

        # Determine if user wants to read a specific email or get a summary
        user_text_lower = user_text.lower()

        # Check if user wants to read a specific email (e.g., "read me the solicitors email")
        is_specific_email = any(keyword in user_text_lower for keyword in ["read me", "read the", "show me the", "open the"])

        try:
            # Fetch emails
            filter_unread = "unread" in user_text_lower

            if filter_unread:
                emails = provider.read_email(folder="inbox", top=20, filter_query="isRead eq false")
                logging.info(f"[EMAIL_HANDLERS] Fetched {len(emails)} unread emails with filter 'isRead eq false'")
            else:
                emails = provider.read_email(folder="inbox", top=50)
                logging.info(f"[EMAIL_HANDLERS] Fetched {len(emails)} emails (no filter)")

            if not emails:
                msg = "You have no unread emails." if filter_unread else "Your inbox is empty."
                return self._format_success_response(msg, "read_email", {"email_count": 0, "filter_unread": filter_unread})

            # If user wants a specific email, search for it
            if is_specific_email:
                return self._read_specific_email(user_text, emails, user_id)

            # Otherwise, generate AI summary of emails
            summary = self._generate_email_summary(emails, user_id, filter_unread)

            return self._format_success_response(
                summary,
                "read_email",
                {"email_count": len(emails), "filter_unread": filter_unread}
            )

        except Exception as e:
            self._log_error("handle_read_email", e)
            return self._format_error_response(
                f"I encountered an error reading your emails: {str(e)}",
                "read_email",
                str(e)
            )

    def _read_specific_email(
        self,
        user_text: str,
        emails: list,
        user_id: int
    ) -> Dict:
        """
        Read a specific email based on user's description.

        Args:
            user_text: User's request (e.g., "read me the solicitors email")
            emails: List of email dictionaries to search
            user_id: User ID

        Returns:
            Response dictionary with email content
        """
        user_text_lower = user_text.lower()

        # Remove common phrases to get the actual search terms
        search_text = user_text_lower
        search_text = re.sub(r'\b(read me|read the|show me|show me the|open the|can you)\b', '', search_text)
        search_text = re.sub(r'\b(the|email|from)\b', '', search_text)
        search_text = search_text.strip()

        logging.info(f"[EMAIL_HANDLERS] Searching for specific email with keywords: '{search_text}'")

        # Search for matching email by subject, sender, or preview
        matching_email = None
        for email in emails:
            subject = email.get("subject", "").lower()
            sender = email.get("from", "").lower()
            preview = email.get("preview", "").lower()

            # Check if search terms appear in subject, sender, or preview
            if search_text in subject or search_text in sender or search_text in preview:
                matching_email = email
                break

            # Also check if individual words match (require at least 2 words to match)
            search_words = [w for w in search_text.split() if len(w) > 3]
            if len(search_words) >= 2:
                matches = sum(1 for word in search_words if word in subject or word in sender or word in preview)
                if matches >= 2:
                    matching_email = email
                    break
            elif search_words:
                # Single significant word - still check
                if any(word in subject or word in sender or word in preview for word in search_words):
                    matching_email = email
                    break

        if not matching_email:
            return self._format_error_response(
                f"I couldn't find an email matching '{search_text}'. Can you be more specific?",
                "read_email"
            )

        # Get the M365 provider to fetch full email body
        provider_result = self._get_provider("read_email", user_id)
        if not provider_result:
            return self._format_error_response("Failed to access email provider.", "read_email")

        provider_id, provider = provider_result

        # Fetch full email body
        try:
            email_id = matching_email.get("id")
            body = provider.get_email_body(email_id)
        except Exception as e:
            logging.warning(f"[EMAIL_HANDLERS] Failed to fetch full email body: {e}")
            body = matching_email.get("preview", "No content available")

        # Format the email for display
        subject = matching_email.get("subject", "No subject")
        sender = matching_email.get("from", "Unknown")
        received = matching_email.get("received_at", "")

        response_text = f"**Email from {sender}**\n\n"
        response_text += f"**Subject:** {subject}\n\n"
        if received:
            response_text += f"**Received:** {received}\n\n"
        response_text += f"**Content:**\n{body}"

        return self._format_success_response(
            response_text,
            "read_email",
            {"email_id": matching_email.get("id"), "subject": subject, "sender": sender}
        )

    def handle_compose_email(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle email composition and reply operations.

        Examples:
        - "reply to the email 'this is a test' with details about my calendar"
        - "send an email to john@example.com about the meeting"
        - "draft an email to the team"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with compose/reply result
        """
        # Check if this is a reply or new email
        is_reply = "reply" in user_text.lower() or "respond" in user_text.lower()

        if is_reply:
            return self.handle_email_reply(user_text, session_id, user_id, context)
        else:
            return self.handle_email_send(user_text, session_id, user_id, context)

    def handle_email_reply(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle replying to an email.

        Steps:
        1. Extract email subject/identifier from user text
        2. Search for matching email in inbox
        3. Generate reply body using LLM (with calendar context if requested)
        4. Create confirmation for sending reply
        """
        # Get provider
        provider_result = self._get_provider("read_email", user_id)
        if not provider_result:
            return self._format_no_provider_response("reply_email", "compose_email", "email")

        provider_id, provider = provider_result

        # Extract email identifier
        # Priority 1: Check for recent proactive email notification in conversation
        # Priority 2: Look for quoted subject text
        matching_email = None

        try:
            # Check for recent proactive email notification
            recent_turns = self.memory.get_recent_turns(session_id, limit=10)
            for turn in reversed(recent_turns):  # Most recent first
                if turn.get("role") == "assistant":
                    metadata = turn.get("metadata", {})
                    if metadata.get("proactive") and metadata.get("type") == "important_email":
                        # Found a proactive email notification - extract email ID
                        source_ids = metadata.get("source_ids", [])
                        if source_ids:
                            email_id = source_ids[0]
                            logging.info(f"[EMAIL_HANDLERS] Found recent proactive email notification with ID: {email_id}")

                            # Fetch the email details
                            emails = provider.read_email(folder="inbox", top=50)
                            for email in emails:
                                if email.get("id") == email_id:
                                    matching_email = email
                                    break

                            if matching_email:
                                logging.info(f"[EMAIL_HANDLERS] Using email from proactive notification: {matching_email.get('subject')}")
                                break
        except Exception as e:
            logging.warning(f"[EMAIL_HANDLERS] Failed to check proactive notifications: {e}")

        # If no proactive email found, look for quoted subject text
        if not matching_email:
            subject_match = re.search(r"['\"]([^'\"]+)['\"]", user_text)

            if not subject_match:
                return self._format_error_response(
                    "I couldn't identify which email to reply to. Either:\n1. Reply immediately after receiving a proactive email notification, or\n2. Specify the email subject in quotes (e.g., \"reply to 'this is a test'\").",
                    "compose_email"
                )

            search_subject = subject_match.group(1)
            logging.info(f"[EMAIL_HANDLERS] Searching for email with subject: {search_subject}")

            try:
                # Read recent emails to find the one to reply to
                emails = provider.read_email(folder="inbox", top=50)

                # Find matching email by subject
                for email in emails:
                    if search_subject.lower() in email.get("subject", "").lower():
                        matching_email = email
                        break

                if not matching_email:
                    return self._format_error_response(
                        f"I couldn't find an email with subject containing '{search_subject}'. Please check the subject and try again.",
                        "compose_email"
                    )
            except Exception as e:
                self._log_error("handle_email_reply", e)
                return self._format_error_response(
                    f"I encountered an error searching for the email: {str(e)}",
                    "compose_email",
                    str(e)
                )

        # At this point, matching_email should be set (either from proactive or subject search)
        if not matching_email:
            return self._format_error_response(
                "I couldn't identify which email to reply to.",
                "compose_email"
            )

        try:
            # Extract what to include in reply (e.g., "with details about my calendar")
            reply_context = user_text.lower()
            include_calendar = "calendar" in reply_context or "schedule" in reply_context

            # Generate reply body using LLM
            reply_body = self._generate_reply_body(
                user_text,
                matching_email,
                user_id,
                include_calendar
            )

            if not reply_body:
                logging.error(f"[EMAIL_HANDLERS] _generate_reply_body returned None for email reply")
                return self._format_error_response(
                    "I couldn't generate a reply. This might be due to missing LLM provider configuration. Please check that you have a provider configured for the 'system' intent.",
                    "compose_email"
                )

            # Create confirmation for sending reply
            if not self.confirmation_manager:
                return self._format_error_response("The confirmation system is not initialized.", "compose_email")

            confirmation_message = f"Reply to '{matching_email.get('subject')}' from {matching_email.get('from')}?"
            preview = reply_body[:200] + "..." if len(reply_body) > 200 else reply_body

            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="reply_email",
                action_params={
                    "email_id": matching_email["id"],
                    "body": reply_body,
                    "content_type": "HTML"
                },
                confirmation_message=f"{confirmation_message}\n\nPreview:\n{preview}",
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_message}\n\nPreview:\n{preview}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "model": None,
                "task_type": "compose_email",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "expires_at": expires_at,
                    "action_type": "reply_email",
                    "action_category": "email"
                }
            }

        except Exception as e:
            self._log_error("handle_email_reply", e)
            return self._format_error_response(
                f"I encountered an error preparing the reply: {str(e)}",
                "compose_email",
                str(e)
            )

    def handle_email_send(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle composing and sending a new email.

        Examples:
        - "send an email to john@example.com saying I'll be late"
        - "email danny@example.com about the meeting tomorrow"
        """
        # Get provider
        provider_result = self._get_provider("send_email", user_id)
        if not provider_result:
            return self._format_no_provider_response("send_email", "compose_email", "email")

        provider_id, provider = provider_result

        # Extract recipient email address
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = re.findall(email_pattern, user_text)

        # Also look for names in quotes or after "to"
        name_pattern = r'(?:to|email)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        name_matches = re.findall(name_pattern, user_text)

        recipient = None
        if email_matches:
            recipient = email_matches[0]
        elif name_matches:
            recipient_name = name_matches[0]

            # Check if user is referring to themselves
            user_name_fact = None
            try:
                facts = self.memory.get_facts(user_id)
                for fact in facts:
                    if fact.get("key", "").lower() in ["my name", "name"]:
                        user_name_fact = fact.get("value", "").lower()
                        break
            except:
                pass

            if user_name_fact and recipient_name.lower() == user_name_fact:
                # User wants to email themselves - get their M365 email
                try:
                    creds = self.memory.get_m365_credentials(user_id)
                    if creds and creds.get("user_principal_name"):
                        recipient = creds["user_principal_name"]
                        logging.info(f"[EMAIL_HANDLERS] Resolved self-reference '{recipient_name}' to {recipient}")
                except Exception as e:
                    logging.warning(f"[EMAIL_HANDLERS] Failed to get user's email: {e}")

            if not recipient:
                # Future enhancement: check M365 contacts/people API
                return self._format_error_response(
                    f"I found the name '{recipient_name}' but don't have their email address. Please provide the email address (e.g., '{recipient_name.lower().replace(' ', '.')}@example.com').",
                    "compose_email"
                )

        if not recipient:
            return self._format_error_response(
                "I couldn't identify the recipient. Please specify an email address (e.g., 'send an email to john@example.com').",
                "compose_email"
            )

        # Generate email subject and body using LLM
        subject, body = self._generate_new_email_body(user_text, recipient, user_id)

        if not subject or not body:
            return self._format_error_response(
                "I couldn't generate the email content. Please try again or provide more details.",
                "compose_email"
            )

        # Create draft in M365 first
        try:
            draft_result = provider.draft_email(
                to=[recipient],
                subject=subject,
                body=body,
                content_type="HTML"
            )
            draft_id = draft_result.get("draft_id")
            logging.info(f"[EMAIL_HANDLERS] Created draft email {draft_id}")
        except Exception as e:
            self._log_error("handle_email_send - draft creation", e)
            return self._format_error_response(f"Failed to create email draft: {str(e)}", "compose_email", str(e))

        # Create confirmation for sending the draft
        confirmation_result = self.confirmation_manager.create_confirmation(
            user_id=user_id,
            session_id=session_id,
            action_type="send_draft_email",
            provider_id=provider_id,
            action_params={
                "draft_id": draft_id
            },
            confirmation_message=f"Send email '{subject}' to {recipient}?"
        )

        if not confirmation_result:
            return self._format_error_response("Failed to create confirmation for email.", "compose_email")

        # Extract just the integer ID for JSON serialization
        confirmation_id = confirmation_result["confirmation_id"]

        # Strip HTML for preview display
        body_preview = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        body_preview = re.sub('<[^<]+?>', '', body_preview)

        # Return confirmation request with metadata for UI widget
        return {
            "text": f"Draft email to {recipient}:\n\nSubject: {subject}\n\nMessage:\n{body_preview}",
            "provider": "action_router",
            "model": None,
            "task_type": "compose_email",
            "metadata": {
                "requires_confirmation": True,
                "confirmation_id": confirmation_id,
                "recipient": recipient,
                "subject": subject,
                "draft_id": draft_id,
                "action_category": "email",
                "confirmation_message": f"Send email '{subject}' to {recipient}?"
            }
        }

    def _generate_reply_body(
        self,
        user_request: str,
        original_email: Dict,
        user_id: int,
        include_calendar: bool = False
    ) -> str:
        """
        Generate email reply body using LLM.

        Args:
            user_request: Original user request
            original_email: Email being replied to
            user_id: User ID
            include_calendar: Whether to include calendar information

        Returns:
            Generated reply body (HTML)
        """
        from core.router import route_request

        try:

            # Get user's name from memory facts
            user_name = None
            try:
                memories = self.memory.get_relevant_memories(user_id, "my name", max_results=5)
                name_mem = next((m for m in memories if m.get('key', '').lower() in ['my name', 'name']), None)
                if name_mem:
                    user_name = name_mem.get('value')
                    logging.info(f"[EMAIL_HANDLERS] Found user name in memory: {user_name}")
            except Exception as e:
                logging.warning(f"[EMAIL_HANDLERS] Failed to fetch user name from memory: {e}")

            # Build context
            context_parts = []

            # Add user's name if available
            if user_name:
                context_parts.append(f"User's name: {user_name}")

            # Add original email context
            context_parts.append(f"Original email from: {original_email.get('from')}")
            context_parts.append(f"Subject: {original_email.get('subject')}")
            context_parts.append(f"Preview: {original_email.get('preview', '')}")

            # Add calendar context if requested
            calendar_info = ""
            if include_calendar:
                # Get this week's calendar events
                now = datetime.now()
                start_of_week = now - timedelta(days=now.weekday())
                end_of_week = start_of_week + timedelta(days=7)

                # Load providers and get calendar
                self.action_registry.load_providers(user_id)
                calendar_providers = self.action_registry.get_providers_by_capability("read_calendar", user_id)

                if calendar_providers:
                    _, cal_provider = calendar_providers[0]
                    try:
                        events = cal_provider.read_calendar(start_of_week, end_of_week)
                        # Filter future events
                        future_events = [
                            e for e in events
                            if e.get("start_time") and datetime.fromisoformat(
                                re.sub(r'\.(\d{6})\d+', r'.\1', e["start_time"]).replace("Z", "+00:00")
                            ) > now
                        ]

                        if future_events:
                            calendar_info = "\n\nUser's calendar this week:\n"
                            for event in future_events[:10]:  # Limit to 10 events
                                start_str = event.get("start_time", "")
                                if start_str:
                                    start_time = datetime.fromisoformat(
                                        re.sub(r'\.(\d{6})\d+', r'.\1', start_str).replace("Z", "+00:00")
                                    )
                                    day_date = start_time.strftime("%A, %B %d at %I:%M %p")
                                    calendar_info += f"- {event.get('subject')} on {day_date}\n"
                    except Exception as e:
                        logging.warning(f"[EMAIL_HANDLERS] Failed to fetch calendar for reply: {e}")

            context_text = "\n".join(context_parts) + calendar_info

            # Construct prompt
            system_prompt = """You are an email assistant helping the user compose a reply.

Generate a professional, friendly email reply based on the user's instructions.

Guidelines:
1. Be concise and professional
2. Use proper email formatting (greeting, body, closing)
3. If calendar information is provided, incorporate it naturally
4. Match the tone of the original email
5. Return ONLY the email body (no subject line)
6. Format as plain text (we'll convert to HTML)
7. IMPORTANT: If the user's name is provided, use it in the sign-off (e.g., "Best regards,\nDanny"). Never use placeholders like "[Your Name]"."""

            user_prompt = f"""User request: {user_request}

{context_text}

Generate a reply email body:"""

            # Use route_request to leverage user's routing preferences
            router_context = {
                "text": user_prompt,
                "session_id": "email_reply_generation",
                "memory": self.memory,
                "user_id": str(user_id),
                "force_intent": "system",  # Use system intent for internal generation
                "system_message": system_prompt
            }

            result = route_request(router_context)
            reply_text = result.get("text", "").strip()

            if not reply_text:
                logging.warning("[EMAIL_HANDLERS] LLM returned empty reply")
                return None

            # Convert to simple HTML
            reply_html = reply_text.replace("\n", "<br>\n")

            logging.info(f"[EMAIL_HANDLERS] Generated reply body ({len(reply_html)} chars)")
            return reply_html

        except Exception as e:
            logging.error(f"[EMAIL_HANDLERS] Reply generation failed: {e}")
            return None

    def _generate_new_email_body(
        self,
        user_request: str,
        recipient: str,
        user_id: int
    ) -> tuple:
        """
        Generate new email subject and body using LLM.

        Args:
            user_request: Original user request
            recipient: Email recipient
            user_id: User ID

        Returns:
            Tuple of (subject, body_html) or (None, None) if generation fails
        """
        from core.router import route_request

        try:

            # Get user's name from memory facts
            user_name = None
            try:
                memories = self.memory.get_relevant_memories(user_id, "my name", max_results=5)
                name_mem = next((m for m in memories if m.get('key', '').lower() in ['my name', 'name']), None)
                if name_mem:
                    user_name = name_mem.get('value')
                    logging.info(f"[EMAIL_HANDLERS] Found user name in memory: {user_name}")
            except Exception as e:
                logging.warning(f"[EMAIL_HANDLERS] Failed to fetch user name from memory: {e}")

            # Build context
            context_parts = []

            # Add user's name if available
            if user_name:
                context_parts.append(f"Sender's name: {user_name}")

            context_parts.append(f"Recipient: {recipient}")

            context_text = "\n".join(context_parts)

            # Construct prompt
            system_prompt = """You are an email generator. Output ONLY in this exact format:

SUBJECT: <subject line>
BODY:
<email content>

CRITICAL:
- Start with "SUBJECT:" then the subject
- Next line: "BODY:"
- Then the email content
- NO extra text, NO explanations, NO "You can..." or "Feel free..."
- Plain text only, NO markdown formatting
- End after signature
- Use sender name from context if provided"""

            # Build user prompt
            signature_instruction = f"Sign with: {user_name}" if user_name else "Generic closing"

            user_prompt = f"""{user_request}

Recipient: {recipient}
{signature_instruction}

Generate email in SUBJECT:/BODY: format:"""

            # Use route_request to respect user's routing preferences
            router_context = {
                "text": user_prompt,
                "session_id": "email_generation",
                "memory": self.memory,
                "user_id": str(user_id) if user_id else "1",
                "forced_provider": None,
                "force_intent": "system",  # Use system intent for internal tasks
                "system_message": system_prompt
            }

            result = route_request(router_context)
            response_text = result.get("text", "").strip()

            # Debug: Log the raw LLM response
            logging.info(f"[EMAIL_HANDLERS] Raw LLM response: {response_text[:500]}")

            # Parse subject and body from response
            subject = None
            body = None

            # Try multiple subject patterns
            subject_match = re.search(r'SUBJECT:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
            if not subject_match:
                # Try without colon
                subject_match = re.search(r'Subject\s+(.+?)(?:\n|$)', response_text, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1).strip()

            # Try multiple body patterns
            body_match = re.search(r'BODY:\s*(.+?)(?:\n\n(?:You can|Feel free|Let me know|If you|Please|Note:|---|Here\'s)|$)', response_text, re.IGNORECASE | re.DOTALL)
            if not body_match:
                # Try without colon
                body_match = re.search(r'Body\s*\n(.+?)(?:\n\n(?:You can|Feel free|Let me know|If you|Please|Note:|---|Here\'s)|$)', response_text, re.IGNORECASE | re.DOTALL)
            if body_match:
                body = body_match.group(1).strip()

            # If body not found with stop pattern, try capturing everything
            if not body:
                body_match = re.search(r'BODY:\s*(.+)', response_text, re.IGNORECASE | re.DOTALL)
                if body_match:
                    full_body = body_match.group(1).strip()
                    # Try to find where email signature ends (common patterns)
                    # Stop at double newline followed by conversational text
                    lines = full_body.split('\n')
                    email_lines = []
                    found_signature = False
                    for i, line in enumerate(lines):
                        email_lines.append(line)
                        # Check if this looks like a signature line
                        if any(closing in line.lower() for closing in ['regards', 'sincerely', 'thanks', 'cheers', 'best']):
                            # Look ahead - if next non-empty line doesn't start with conversational text, include it
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line and not any(phrase in next_line.lower() for phrase in ['you can', 'feel free', 'let me know', 'if you', 'please']):
                                    email_lines.append(lines[i + 1])
                            found_signature = True
                            break

                    if found_signature:
                        body = '\n'.join(email_lines).strip()
                    else:
                        body = full_body

            if not subject or not body:
                logging.error(f"[EMAIL_HANDLERS] Failed to parse subject/body from LLM response")
                return None, None

            # Strip any markdown formatting that might have slipped through
            def strip_markdown(text):
                """Remove common markdown formatting characters."""
                # Remove bold/italic markers
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
                text = re.sub(r'__(.+?)__', r'\1', text)      # __bold__
                text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
                text = re.sub(r'_(.+?)_', r'\1', text)        # _italic_
                # Remove leading/trailing asterisks or underscores
                text = text.strip('*_')
                return text

            subject = strip_markdown(subject)
            body = strip_markdown(body)

            # Replace any remaining placeholders with actual name
            if user_name:
                body = re.sub(r'\[Your [Nn]ame\]', user_name, body)
                body = re.sub(r'\[Sender\]', user_name, body)
                body = re.sub(r'\[Your [Nn]ame [Hh]ere\]', user_name, body)

            # Convert to simple HTML
            body_html = body.replace("\n", "<br>\n")

            logging.info(f"[EMAIL_HANDLERS] Generated email: subject='{subject}' body=({len(body_html)} chars)")
            return subject, body_html

        except Exception as e:
            logging.error(f"[EMAIL_HANDLERS] Email generation failed: {e}")
            return None, None

    def _generate_email_summary(self, emails: list, user_id: int, unread_only: bool = False) -> str:
        """
        Generate an AI summary of emails using LLM.

        Args:
            emails: List of email dictionaries
            user_id: User ID for context
            unread_only: Whether these are unread emails only

        Returns:
            AI-generated summary of emails
        """
        from providers.openai import OpenAIProvider
        from providers.anthropic import AnthropicProvider
        from providers.gemini import GoogleProvider
        from providers.grok import XAIProvider
        from providers.mistral import MistralProvider
        from core.provider_registry import ProviderRegistry

        try:
            # Get system provider for lightweight tasks (configurable)
            registry = ProviderRegistry(self.memory)

            # First check for "system" routing preference
            system_provider_id = self.memory.get_routing_provider(user_id, "system") if self.memory else None
            provider_cfg = None

            if system_provider_id:
                # Use configured system provider
                provider_cfg = registry.get(system_provider_id)
                logging.info(f"[EMAIL_HANDLERS] Using configured system provider: {system_provider_id}")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Try configured fallback provider for system intent
                fallback_provider_id = self.memory.get_fallback_provider(user_id, "system") if self.memory else None
                if fallback_provider_id:
                    provider_cfg = registry.get(fallback_provider_id)
                    if provider_cfg and provider_cfg.get("api_key"):
                        logging.info(f"[EMAIL_HANDLERS] Using configured fallback provider: {fallback_provider_id}")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Fallback to OpenAI provider
                provider_cfg = registry.get_by_type("openai")
                logging.info("[EMAIL_HANDLERS] Using fallback OpenAI provider for email summarization")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # No LLM available at all
                logging.warning("[EMAIL_HANDLERS] No LLM provider available, using basic email list")
                return self._format_email_list(emails, unread_only)

            # Instantiate appropriate provider based on type
            provider_type = provider_cfg.get("type", "openai")
            if provider_type == "openai":
                provider = OpenAIProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model") or "gpt-4o-mini"
                )
            elif provider_type == "anthropic":
                provider = AnthropicProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "google":
                provider = GoogleProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "xai":
                provider = XAIProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "mistral":
                provider = MistralProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            else:
                # Unknown provider type
                logging.warning(f"[EMAIL_HANDLERS] Provider type {provider_type} not supported for lightweight tasks, using basic email list")
                return self._format_email_list(emails, unread_only)

            # Build email context for LLM
            email_context = []
            for email in emails:
                email_context.append(
                    f"From: {email.get('from', 'Unknown')}\n"
                    f"Subject: {email.get('subject', 'No subject')}\n"
                    f"Preview: {email.get('preview', '')}\n"
                    f"Received: {email.get('received_at', '')}"
                )

            emails_text = "\n\n---\n\n".join(email_context)

            # Construct summarization prompt
            filter_text = "unread " if unread_only else ""
            logging.info(f"[EMAIL_HANDLERS] Generating summary for {len(emails)} {filter_text}emails")
            system_prompt = f"""You are an email assistant. Provide a brief, conversational summary of the user's {filter_text}emails.

Rules:
1. Start with EXACTLY the count I give you (e.g., "You have 4 unread emails" if I provide 4 emails)
2. Group by theme/sender when possible (e.g., "2 from your team about the project")
3. Mention only the MOST important or urgent items
4. Maximum 2-3 sentences total
5. Be natural and conversational
6. Avoid dates, order numbers, and excessive detail
7. CRITICAL: Use the EXACT email count - do not estimate or round

Example: "You have 4 unread emails. Most are newsletters and notifications. There's an urgent message from Sarah about tomorrow's meeting."

Focus on what matters. Be concise."""

            user_prompt = f"Here are EXACTLY {len(emails)} {filter_text}emails. Provide a brief summary starting with 'You have {len(emails)} {filter_text}emails':\n\n{emails_text}"

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Extract text from response
            summary_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            logging.info(f"[EMAIL_HANDLERS] Generated email summary for {len(emails)} emails")
            return summary_text

        except Exception as e:
            logging.error(f"[EMAIL_HANDLERS] Email summary generation failed: {e}")
            # Fallback to basic formatting
            return self._format_email_list(emails, unread_only)

    def _format_email_list(self, emails: list, unread_only: bool = False) -> str:
        """
        Format emails as a basic list (fallback when LLM unavailable).

        Args:
            emails: List of email dictionaries
            unread_only: Whether these are unread emails only

        Returns:
            Formatted string with email list
        """
        filter_text = "unread " if unread_only else ""
        header = f"You have {len(emails)} {filter_text}email{'s' if len(emails) != 1 else ''}:\n\n"

        formatted = []
        for email in emails[:10]:  # Limit to first 10
            subject = email.get("subject", "No subject")
            sender = email.get("from", "Unknown")
            formatted.append(f"• {subject} (from {sender})")

        if len(emails) > 10:
            formatted.append(f"\n...and {len(emails) - 10} more")

        return header + "\n".join(formatted)
