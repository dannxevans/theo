"""
Microsoft 365 (Graph API) action provider.

Handles calendar and email operations using Microsoft Graph API.
Requires OAuth 2.0 credentials (access token + refresh token).

Supported capabilities:
- read_calendar: Fetch calendar events
- create_calendar_event: Create new calendar events
- update_calendar_event: Modify existing events
- delete_calendar_event: Delete events
- read_email: Read inbox messages
- send_email: Send emails
- reply_email: Reply to emails
- draft_email: Create email drafts
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from actions.base import (
    ActionProvider,
    ActionProviderError,
    ActionValidationError,
    ActionAuthenticationError,
    ActionExecutionError
)
import logging


class M365Provider(ActionProvider):
    """
    Microsoft 365 (Graph API) action provider.

    Handles calendar and email operations through Microsoft Graph API.
    """

    name = "m365"
    capabilities = [
        "read_calendar",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "read_email",
        "send_email",
        "reply_email",
        "draft_email",
    ]

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str, refresh_token: str, expires_at: datetime, user_id: int = None, memory_store = None):
        """
        Initialize M365 provider with OAuth credentials.

        Args:
            access_token: Microsoft Graph API access token
            refresh_token: Refresh token for obtaining new access tokens
            expires_at: Datetime when access token expires
            user_id: User ID for storing refreshed tokens
            memory_store: Memory store instance for persisting tokens
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.user_id = user_id
        self.memory_store = memory_store

    # =============================
    # Health & Validation
    # =============================

    def check_health(self) -> Dict[str, Any]:
        """Test connectivity to Microsoft Graph API."""
        try:
            self._ensure_token_valid()
            headers = self._get_headers()

            # Simple health check: fetch user profile
            response = requests.get(
                f"{self.GRAPH_API_BASE}/me",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "healthy": True,
                    "status": "connected",
                    "last_check": datetime.utcnow(),
                    "user_principal_name": user_data.get("userPrincipalName")
                }
            else:
                return {
                    "healthy": False,
                    "status": "error",
                    "last_check": datetime.utcnow(),
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except ActionAuthenticationError as e:
            return {
                "healthy": False,
                "status": "auth_error",
                "last_check": datetime.utcnow(),
                "error": str(e)
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "error",
                "last_check": datetime.utcnow(),
                "error": str(e)
            }

    def validate_params(self, action_type: str, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate parameters for each action type."""
        validators = {
            "read_calendar": self._validate_read_calendar,
            "create_calendar_event": self._validate_create_event,
            "update_calendar_event": self._validate_update_event,
            "delete_calendar_event": self._validate_delete_event,
            "read_email": self._validate_read_email,
            "send_email": self._validate_send_email,
            "reply_email": self._validate_reply_email,
            "draft_email": self._validate_draft_email,
        }

        validator = validators.get(action_type)
        if not validator:
            return False, f"Unknown action type: {action_type}"

        return validator(params)

    # =============================
    # Calendar Operations
    # =============================

    def read_calendar(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Fetch calendar events within date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of event dictionaries in THEO normalized format

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()

        # Build query parameters for date range
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()

        url = f"{self.GRAPH_API_BASE}/me/calendarView"
        params = {
            "startDateTime": start_iso,
            "endDateTime": end_iso,
            "$select": "id,subject,start,end,location,attendees,importance,isAllDay,bodyPreview",
            "$orderby": "start/dateTime"
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            events = data.get("value", [])

            # Normalize to THEO format
            return [self._normalize_event(e) for e in events]

        except requests.HTTPError as e:
            logging.error(f"[M365] Calendar read failed: {e}")
            raise ActionExecutionError(f"Failed to read calendar: {e}")

    def create_calendar_event(
        self,
        subject: str,
        start_time: datetime,
        end_time: datetime,
        location: str = None,
        description: str = None,
        attendees: List[str] = None
    ) -> Dict:
        """
        Create a new calendar event.

        Args:
            subject: Event title
            start_time: Start datetime
            end_time: End datetime
            location: Event location (optional)
            description: Event description (optional)
            attendees: List of attendee email addresses (optional)

        Returns:
            Created event details in THEO normalized format

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()

        event_data = {
            "subject": subject,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "UTC"
            }
        }

        if location:
            event_data["location"] = {"displayName": location}

        if description:
            event_data["body"] = {
                "contentType": "text",
                "content": description
            }

        if attendees:
            event_data["attendees"] = [
                {
                    "emailAddress": {"address": email},
                    "type": "required"
                }
                for email in attendees
            ]

        url = f"{self.GRAPH_API_BASE}/me/calendar/events"

        try:
            response = requests.post(url, headers=headers, json=event_data, timeout=15)
            response.raise_for_status()

            created_event = response.json()
            logging.info(f"[M365] Created calendar event: {created_event.get('id')}")

            return self._normalize_event(created_event)

        except requests.HTTPError as e:
            logging.error(f"[M365] Calendar event creation failed: {e}")
            raise ActionExecutionError(f"Failed to create calendar event: {e}")

    def update_calendar_event(self, event_id: str, updates: Dict) -> Dict:
        """
        Update an existing calendar event.

        Args:
            event_id: Microsoft Graph event ID
            updates: Dictionary of fields to update

        Returns:
            Updated event in THEO normalized format

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()
        url = f"{self.GRAPH_API_BASE}/me/calendar/events/{event_id}"

        try:
            response = requests.patch(url, headers=headers, json=updates, timeout=15)
            response.raise_for_status()

            updated_event = response.json()
            logging.info(f"[M365] Updated calendar event: {event_id}")

            return self._normalize_event(updated_event)

        except requests.HTTPError as e:
            logging.error(f"[M365] Calendar event update failed: {e}")
            raise ActionExecutionError(f"Failed to update calendar event: {e}")

    def delete_calendar_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.

        Args:
            event_id: Microsoft Graph event ID

        Returns:
            True if deletion successful

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()
        url = f"{self.GRAPH_API_BASE}/me/calendar/events/{event_id}"

        try:
            response = requests.delete(url, headers=headers, timeout=15)
            response.raise_for_status()

            logging.info(f"[M365] Deleted calendar event: {event_id}")
            return True

        except requests.HTTPError as e:
            logging.error(f"[M365] Calendar event deletion failed: {e}")
            raise ActionExecutionError(f"Failed to delete calendar event: {e}")

    # =============================
    # Email Operations
    # =============================

    def read_email(
        self,
        folder: str = "inbox",
        top: int = 10,
        filter_query: str = None
    ) -> List[Dict]:
        """
        Read emails from a folder.

        Args:
            folder: Mail folder ("inbox", "sentitems", "drafts", etc.)
            top: Maximum number of messages to retrieve
            filter_query: OData filter query (e.g., "isRead eq false")

        Returns:
            List of email dictionaries in THEO normalized format

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()
        url = f"{self.GRAPH_API_BASE}/me/mailFolders/{folder}/messages"

        params = {
            "$top": top,
            "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,importance",
            "$orderby": "receivedDateTime DESC"
        }

        if filter_query:
            params["$filter"] = filter_query

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            emails = data.get("value", [])

            return [self._normalize_email(e) for e in emails]

        except requests.HTTPError as e:
            logging.error(f"[M365] Email read failed: {e}")
            raise ActionExecutionError(f"Failed to read emails: {e}")

    def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str] = None,
        bcc: List[str] = None,
        content_type: str = "HTML"
    ) -> Dict:
        """
        Send an email.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)
            content_type: "HTML" or "Text" (default: "HTML")

        Returns:
            Dictionary with send status

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()

        message = {
            "subject": subject,
            "body": {
                "contentType": content_type,
                "content": body
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in to
            ]
        }

        if cc:
            message["ccRecipients"] = [
                {"emailAddress": {"address": email}} for email in cc
            ]

        if bcc:
            message["bccRecipients"] = [
                {"emailAddress": {"address": email}} for email in bcc
            ]

        payload = {"message": message, "saveToSentItems": "true"}

        url = f"{self.GRAPH_API_BASE}/me/sendMail"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()

            logging.info(f"[M365] Sent email to {to}")

            return {
                "status": "sent",
                "subject": subject,
                "to": to,
                "sent_at": datetime.utcnow().isoformat()
            }

        except requests.HTTPError as e:
            logging.error(f"[M365] Email send failed: {e}")
            raise ActionExecutionError(f"Failed to send email: {e}")

    def draft_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        content_type: str = "HTML"
    ) -> Dict:
        """
        Create a draft email (not sent).

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            content_type: "HTML" or "Text" (default: "HTML")

        Returns:
            Dictionary with draft details

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()

        message = {
            "subject": subject,
            "body": {
                "contentType": content_type,
                "content": body
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in to
            ]
        }

        url = f"{self.GRAPH_API_BASE}/me/messages"

        try:
            response = requests.post(url, headers=headers, json=message, timeout=15)
            response.raise_for_status()

            draft = response.json()
            logging.info(f"[M365] Created email draft: {draft.get('id')}")

            return {
                "status": "draft",
                "draft_id": draft.get("id"),
                "subject": subject,
                "to": to,
                "created_at": datetime.utcnow().isoformat()
            }

        except requests.HTTPError as e:
            logging.error(f"[M365] Email draft creation failed: {e}")
            raise ActionExecutionError(f"Failed to create email draft: {e}")

    def reply_email(
        self,
        email_id: str,
        body: str,
        content_type: str = "HTML"
    ) -> Dict:
        """
        Reply to an email.

        Args:
            email_id: ID of the email to reply to
            body: Reply body content
            content_type: "HTML" or "Text" (default: "HTML")

        Returns:
            Dictionary with reply status

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()

        message = {
            "comment": body
        }

        url = f"{self.GRAPH_API_BASE}/me/messages/{email_id}/reply"

        try:
            response = requests.post(url, headers=headers, json=message, timeout=15)
            response.raise_for_status()

            logging.info(f"[M365] Replied to email: {email_id}")

            return {
                "status": "sent",
                "email_id": email_id,
                "sent_at": datetime.utcnow().isoformat()
            }

        except requests.HTTPError as e:
            logging.error(f"[M365] Email reply failed: {e}")
            raise ActionExecutionError(f"Failed to reply to email: {e}")

    def get_email_body(self, email_id: str) -> str:
        """
        Get the full body of an email by ID.

        Args:
            email_id: ID of the email to fetch

        Returns:
            Email body content as text

        Raises:
            ActionAuthenticationError: If token is invalid
            ActionExecutionError: If API call fails
        """
        self._ensure_token_valid()

        headers = self._get_headers()
        url = f"{self.GRAPH_API_BASE}/me/messages/{email_id}"

        params = {
            "$select": "body"
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            body_data = data.get("body", {})
            body_content = body_data.get("content", "")

            # Strip HTML tags if content type is HTML
            content_type = body_data.get("contentType", "")
            if content_type == "html":
                # Simple HTML tag removal (could use a library like BeautifulSoup for more robust parsing)
                import re
                body_content = re.sub('<[^<]+?>', '', body_content)
                body_content = body_content.replace('&nbsp;', ' ')
                body_content = body_content.replace('&amp;', '&')
                body_content = body_content.replace('&lt;', '<')
                body_content = body_content.replace('&gt;', '>')

            logging.info(f"[M365] Fetched full body for email: {email_id}")
            return body_content.strip()

        except requests.HTTPError as e:
            logging.error(f"[M365] Failed to fetch email body: {e}")
            raise ActionExecutionError(f"Failed to fetch email body: {e}")

    # =============================
    # Helper Methods
    # =============================

    def _get_headers(self) -> Dict[str, str]:
        """Build HTTP headers with auth token."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _ensure_token_valid(self):
        """
        Check if token needs refresh and automatically refresh if expired.

        Raises:
            ActionAuthenticationError: If token is expired and can't be refreshed
        """
        # Add buffer of 5 minutes to refresh before actual expiration
        if datetime.utcnow() >= (self.expires_at - timedelta(minutes=5)):
            logging.info("[M365] Access token expired or expiring soon, attempting refresh...")

            # Import M365OAuth here to avoid circular imports
            from auth.m365_oauth import M365OAuth

            # Attempt to refresh token
            new_token_data = M365OAuth.refresh_access_token(self.refresh_token)

            if not new_token_data:
                raise ActionAuthenticationError(
                    "Access token expired and refresh failed. Please reconnect your Microsoft 365 account."
                )

            # Update instance variables
            self.access_token = new_token_data["access_token"]
            self.refresh_token = new_token_data["refresh_token"]
            self.expires_at = new_token_data["expires_at"]

            logging.info(f"[M365] Token refreshed successfully. New expiry: {self.expires_at}")

            # Persist refreshed tokens to database if we have user_id and memory_store
            if self.user_id and self.memory_store:
                try:
                    self.memory_store.store_m365_credentials(
                        user_id=self.user_id,
                        access_token=self.access_token,
                        refresh_token=self.refresh_token,
                        expires_at=self.expires_at
                    )
                    logging.info("[M365] Refreshed tokens persisted to database")
                except Exception as e:
                    logging.error(f"[M365] Failed to persist refreshed tokens: {e}")
                    # Don't fail the operation if we can't persist - tokens are still valid in memory

    def _normalize_event(self, event: Dict) -> Dict:
        """Normalize Microsoft Graph event to THEO format."""
        return {
            "id": event.get("id"),
            "subject": event.get("subject"),
            "start_time": event.get("start", {}).get("dateTime"),
            "end_time": event.get("end", {}).get("dateTime"),
            "location": event.get("location", {}).get("displayName"),
            "description": event.get("bodyPreview"),
            "attendees": [
                a.get("emailAddress", {}).get("address")
                for a in event.get("attendees", [])
            ],
            "is_all_day": event.get("isAllDay", False),
            "importance": event.get("importance"),
        }

    def _normalize_email(self, email: Dict) -> Dict:
        """Normalize Microsoft Graph email to THEO format."""
        return {
            "id": email.get("id"),
            "subject": email.get("subject"),
            "from": email.get("from", {}).get("emailAddress", {}).get("address"),
            "received_at": email.get("receivedDateTime"),
            "preview": email.get("bodyPreview"),
            "is_read": email.get("isRead", False),
            "importance": email.get("importance"),
        }

    # =============================
    # Validation Methods
    # =============================

    def _validate_read_calendar(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate read_calendar parameters."""
        required = ["start_date", "end_date"]
        for field in required:
            if field not in params:
                return False, f"Missing required field: {field}"

        # Validate date types
        if not isinstance(params.get("start_date"), datetime):
            return False, "start_date must be a datetime object"
        if not isinstance(params.get("end_date"), datetime):
            return False, "end_date must be a datetime object"

        # Validate date range
        if params["end_date"] <= params["start_date"]:
            return False, "end_date must be after start_date"

        return True, None

    def _validate_create_event(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate create_calendar_event parameters."""
        required = ["subject", "start_time", "end_time"]
        for field in required:
            if field not in params:
                return False, f"Missing required field: {field}"

        # Validate times
        if not isinstance(params.get("start_time"), datetime):
            return False, "start_time must be a datetime object"
        if not isinstance(params.get("end_time"), datetime):
            return False, "end_time must be a datetime object"

        if params["end_time"] <= params["start_time"]:
            return False, "end_time must be after start_time"

        # Validate attendees if provided
        if "attendees" in params and params["attendees"]:
            if not isinstance(params["attendees"], list):
                return False, "attendees must be a list"

        return True, None

    def _validate_update_event(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate update_calendar_event parameters."""
        if "event_id" not in params:
            return False, "Missing required field: event_id"

        if "updates" not in params:
            return False, "Missing required field: updates"

        if not isinstance(params["updates"], dict):
            return False, "updates must be a dictionary"

        return True, None

    def _validate_delete_event(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate delete_calendar_event parameters."""
        if "event_id" not in params:
            return False, "Missing required field: event_id"

        return True, None

    def _validate_read_email(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate read_email parameters."""
        # All parameters are optional with defaults
        if "top" in params:
            if not isinstance(params["top"], int) or params["top"] <= 0:
                return False, "top must be a positive integer"

        return True, None

    def _validate_send_email(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate send_email parameters."""
        required = ["to", "subject", "body"]
        for field in required:
            if field not in params:
                return False, f"Missing required field: {field}"

        if not params.get("to"):
            return False, "to field must contain at least one recipient"

        if not isinstance(params["to"], list):
            return False, "to must be a list of email addresses"

        return True, None

    def _validate_reply_email(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate reply_email parameters."""
        required = ["email_id", "body"]
        for field in required:
            if field not in params:
                return False, f"Missing required field: {field}"

        if not params.get("email_id"):
            return False, "email_id must be provided"

        if not params.get("body"):
            return False, "body must be provided"

        return True, None

    def _validate_draft_email(self, params: Dict) -> Tuple[bool, Optional[str]]:
        """Validate draft_email parameters."""
        # Same as send_email
        return self._validate_send_email(params)
