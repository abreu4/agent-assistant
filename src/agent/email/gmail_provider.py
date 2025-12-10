"""Gmail OAuth2 provider implementation with embedded credentials and multi-account support."""

import base64
import pickle
from pathlib import Path
from typing import List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

from .provider import EmailProvider, Email
from .account_manager import get_account_manager
from src.utils.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Embedded OAuth credentials (no user setup needed!)
EMBEDDED_CLIENT_CONFIG = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}


class GmailProvider(EmailProvider):
    """Gmail OAuth2 provider with embedded credentials.

    Supports multiple accounts with browser-based OAuth authentication.
    No credential files required - uses embedded OAuth config.
    """

    def __init__(self, account_email: Optional[str] = None):
        """Initialize Gmail provider for specific account.

        Args:
            account_email: Email address of account to use.
                          If None, uses current account from AccountManager.

        Raises:
            ValueError: If no account specified and no current account set
        """
        self.account_manager = get_account_manager()

        # Determine which account to use
        if account_email is None:
            account = self.account_manager.get_current_account()
            if account is None:
                raise ValueError("No current account set")
            account_email = account.email

        self.account_email = account_email
        self.token_path = self.account_manager.get_token_path(account_email)

        # OAuth scopes (read-only)
        self.scopes = config.get(
            'job_agent.email.scopes',
            ['https://www.googleapis.com/auth/gmail.readonly']
        )

        # Gmail API service (lazy-loaded)
        self.service = None
        self.creds = None

        logger.debug(f"GmailProvider initialized for {account_email}")

    def authenticate(self) -> bool:
        """Authenticate using embedded credentials + browser OAuth.

        Loads existing token if available, refreshes if expired, or initiates
        new OAuth2 flow using embedded credentials. Saves token for future use.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # Load existing token
            if self.token_path.exists():
                logger.info(f"Loading token for {self.account_email}...")
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)

            # Refresh or get new credentials
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info(f"Refreshing token for {self.account_email}...")
                    self.creds.refresh(Request())
                else:
                    # Use embedded credentials (no file needed!)
                    logger.info(f"Starting OAuth flow for {self.account_email}...")
                    flow = InstalledAppFlow.from_client_config(
                        EMBEDDED_CLIENT_CONFIG,
                        self.scopes
                    )

                    # Browser-based OAuth flow
                    self.creds = flow.run_local_server(port=0)

                # Save token
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
                logger.debug(f"Token saved for {self.account_email}")

            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.creds)
            logger.info(f"✓ Authenticated as {self.account_email}")
            return True

        except Exception as e:
            logger.error(f"Authentication failed for {self.account_email}: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if Gmail service is ready.

        Returns:
            bool: True if service is initialized and ready
        """
        return self.service is not None

    def fetch_emails(
        self,
        max_results: int = 100,
        query: Optional[str] = None
    ) -> List[Email]:
        """Fetch emails from Gmail.

        Args:
            max_results: Maximum number of emails to fetch
            query: Gmail search query (e.g., "newer_than:30d")

        Returns:
            List[Email]: List of parsed email objects
        """
        if not self.is_authenticated():
            logger.warning(f"Not authenticated, attempting authentication for {self.account_email}...")
            if not self.authenticate():
                logger.error(f"Cannot fetch emails: authentication failed for {self.account_email}")
                return []

        try:
            # Use config query if not provided
            if query is None:
                query = config.get('job_agent.email.query_filter', 'newer_than:30d')

            logger.info(f"Fetching emails for {self.account_email}: query='{query}', max={max_results}")

            # List messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} messages for {self.account_email}")

            # Fetch full message data
            emails = []
            for msg in messages:
                email = self.get_email_by_id(msg['id'])
                if email:
                    # Add account email to Email object
                    email.account_email = self.account_email
                    emails.append(email)

            logger.info(f"✓ Fetched {len(emails)} emails from {self.account_email}")
            return emails

        except Exception as e:
            logger.error(f"Failed to fetch emails from {self.account_email}: {e}")
            return []

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Fetch and parse single email by ID.

        Args:
            email_id: Gmail message ID

        Returns:
            Optional[Email]: Parsed email object or None if failed
        """
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            email = self._parse_message(msg)
            if email:
                email.account_email = self.account_email
            return email

        except Exception as e:
            logger.error(f"Failed to fetch email {email_id}: {e}")
            return None

    def _parse_message(self, msg: dict) -> Email:
        """Parse Gmail API message into Email object.

        Args:
            msg: Gmail API message dict

        Returns:
            Email: Parsed email object
        """
        # Extract headers
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}

        # Parse body (plain text and HTML)
        body_plain, body_html = self._extract_body(msg['payload'])

        # Clean HTML to text if no plain text
        if not body_plain and body_html:
            body_plain = self._html_to_text(body_html)

        # Parse date
        date_str = headers.get('Date', '')
        try:
            email_date = parsedate_to_datetime(date_str)
        except Exception:
            from datetime import datetime
            email_date = datetime.now()

        return Email(
            id=msg['id'],
            thread_id=msg['threadId'],
            sender=headers.get('From', ''),
            recipient=headers.get('To', ''),
            subject=headers.get('Subject', ''),
            body=body_plain or '',
            html_body=body_html,
            date=email_date,
            labels=msg.get('labelIds', []),
            account_email=self.account_email  # Track source account
        )

    def _extract_body(self, payload: dict) -> tuple:
        """Extract plain and HTML body from message payload.

        Handles multipart MIME messages and nested parts.

        Args:
            payload: Gmail message payload dict

        Returns:
            tuple: (plain_text_body, html_body)
        """
        body_plain = ''
        body_html = ''

        # Handle multipart
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')

                # Handle nested multipart
                if 'parts' in part:
                    nested_plain, nested_html = self._extract_body(part)
                    if nested_plain:
                        body_plain = nested_plain
                    if nested_html:
                        body_html = nested_html
                elif mime_type == 'text/plain':
                    body_plain = self._decode_body(part.get('body', {}))
                elif mime_type == 'text/html':
                    body_html = self._decode_body(part.get('body', {}))
        else:
            # Single part
            body_plain = self._decode_body(payload.get('body', {}))

        return body_plain, body_html

    def _decode_body(self, body_data: dict) -> str:
        """Decode base64 body data.

        Args:
            body_data: Gmail API body data dict

        Returns:
            str: Decoded body text
        """
        data = body_data.get('data', '')
        if data:
            try:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Failed to decode body data: {e}")
                return ''
        return ''

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text using BeautifulSoup.

        Args:
            html: HTML content

        Returns:
            str: Plain text extracted from HTML
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            return soup.get_text(separator='\n', strip=True)
        except Exception as e:
            logger.warning(f"Failed to parse HTML: {e}")
            # Fallback: try html.parser
            try:
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text(separator='\n', strip=True)
            except Exception:
                return html  # Return raw HTML as last resort
