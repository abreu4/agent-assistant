"""Microsoft Outlook OAuth2 provider implementation using Microsoft Graph API."""

import os
import pickle
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from msal import PublicClientApplication
import requests
from bs4 import BeautifulSoup

from .provider import EmailProvider, Email
from .account_manager import get_account_manager
from src.utils.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _get_oauth_config() -> dict:
    """Get OAuth configuration from environment variables.

    Returns:
        dict: OAuth client configuration

    Raises:
        ValueError: If credentials not configured in .env
    """
    client_id = os.getenv('OUTLOOK_CLIENT_ID')

    if not client_id:
        raise ValueError(
            "Outlook OAuth credentials not configured!\n"
            "Please set OUTLOOK_CLIENT_ID in your .env file.\n"
            "Get credentials from: https://portal.azure.com"
        )

    return {
        'client_id': client_id,
        'authority': config.get(
            'job_agent.email.outlook.authority',
            'https://login.microsoftonline.com/consumers'
        )
    }


class OutlookProvider(EmailProvider):
    """Microsoft Outlook OAuth2 provider with Graph API integration.

    Supports personal Outlook.com accounts with browser-based OAuth authentication.
    Uses Microsoft Graph API v1.0 for email access.
    """

    def __init__(self, account_email: Optional[str] = None):
        """Initialize Outlook provider for specific account.

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
            'job_agent.email.outlook.scopes',
            [
                'https://graph.microsoft.com/Mail.Read',
                'https://graph.microsoft.com/User.Read'
            ]
        )

        # Graph API endpoint
        self.graph_endpoint = config.get(
            'job_agent.email.outlook.graph_endpoint',
            'https://graph.microsoft.com/v1.0'
        )

        # MSAL app and token (lazy-loaded)
        self.app = None
        self.token_data = None

        logger.debug(f"OutlookProvider initialized for {account_email}")

    def authenticate(self) -> bool:
        """Authenticate using MSAL + browser OAuth.

        Loads existing token if available, refreshes if expired, or initiates
        new OAuth2 flow using MSAL. Saves token for future use.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # Get OAuth config
            oauth_config = _get_oauth_config()

            # Create MSAL PublicClientApplication
            self.app = PublicClientApplication(
                oauth_config['client_id'],
                authority=oauth_config['authority']
            )

            # Load existing token
            self.token_data = self._load_token()

            # Check if token is valid
            if self.token_data and not self._is_token_expired(self.token_data):
                logger.info(f"Using existing token for {self.account_email}")
                return True

            # Try to refresh token
            if self.token_data and 'refresh_token' in self.token_data:
                logger.info(f"Refreshing token for {self.account_email}...")
                refreshed = self._refresh_token(self.token_data)
                if refreshed:
                    self.token_data = refreshed
                    self._save_token(self.token_data)
                    logger.info(f"✓ Token refreshed for {self.account_email}")
                    return True

            # Need new OAuth flow
            logger.info(f"Starting OAuth flow for {self.account_email}...")
            result = self.app.acquire_token_interactive(
                scopes=self.scopes,
                prompt='select_account'
            )

            if 'access_token' not in result:
                error = result.get('error_description', 'Unknown error')
                logger.error(f"Authentication failed: {error}")
                return False

            # Add timestamp for expiration tracking
            result['acquired_at'] = time.time()

            # Save token
            self.token_data = result
            self._save_token(self.token_data)
            logger.info(f"✓ Authenticated as {self.account_email}")
            return True

        except Exception as e:
            logger.error(f"Authentication failed for {self.account_email}: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if provider is authenticated and token is valid.

        Returns:
            bool: True if authenticated with valid token
        """
        if self.token_data is None:
            return False

        if self._is_token_expired(self.token_data):
            # Try to refresh
            if 'refresh_token' in self.token_data:
                refreshed = self._refresh_token(self.token_data)
                if refreshed:
                    self.token_data = refreshed
                    self._save_token(self.token_data)
                    return True
            return False

        return True

    def fetch_emails(
        self,
        max_results: int = 100,
        query: Optional[str] = None
    ) -> List[Email]:
        """Fetch emails from Outlook via Microsoft Graph API.

        Args:
            max_results: Maximum number of emails to fetch
            query: Gmail-style query (will be translated to Graph filter)

        Returns:
            List[Email]: List of parsed email objects
        """
        if not self.is_authenticated():
            logger.warning(f"Not authenticated, attempting authentication for {self.account_email}...")
            if not self.authenticate():
                logger.error(f"Cannot fetch emails: authentication failed for {self.account_email}")
                return []

        try:
            # Translate Gmail-style query to Graph API filter
            graph_filter = self._translate_query(query) if query else None

            logger.info(f"Fetching emails for {self.account_email}: max={max_results}")

            # Build request URL
            url = f"{self.graph_endpoint}/me/messages"
            params = {
                '$top': min(max_results, 999),  # Graph API max per request
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,conversationId,subject,from,toRecipients,receivedDateTime,body,categories,hasAttachments'
            }

            if graph_filter:
                params['$filter'] = graph_filter

            # Fetch emails with pagination
            emails = []
            while url and len(emails) < max_results:
                headers = {'Authorization': f"Bearer {self.token_data['access_token']}"}

                response = requests.get(
                    url,
                    headers=headers,
                    params=params if url == f"{self.graph_endpoint}/me/messages" else None
                )
                response.raise_for_status()
                data = response.json()

                # Parse messages
                for msg in data.get('value', []):
                    if len(emails) >= max_results:
                        break
                    email = self._parse_message(msg)
                    if email:
                        emails.append(email)

                # Check for next page
                url = data.get('@odata.nextLink')

            logger.info(f"✓ Fetched {len(emails)} emails from {self.account_email}")
            return emails

        except Exception as e:
            logger.error(f"Failed to fetch emails from {self.account_email}: {e}")
            return []

    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Fetch single email by ID from Graph API.

        Args:
            email_id: Graph API message ID

        Returns:
            Optional[Email]: Parsed email object or None if failed
        """
        if not self.is_authenticated():
            logger.warning("Not authenticated")
            return None

        try:
            url = f"{self.graph_endpoint}/me/messages/{email_id}"
            params = {
                '$select': 'id,conversationId,subject,from,toRecipients,receivedDateTime,body,categories,hasAttachments'
            }
            headers = {'Authorization': f"Bearer {self.token_data['access_token']}"}

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            msg = response.json()

            email = self._parse_message(msg)
            return email

        except Exception as e:
            logger.error(f"Failed to fetch email {email_id}: {e}")
            return None

    def _parse_message(self, msg: dict) -> Email:
        """Parse Graph API message into Email object.

        Args:
            msg: Graph API message dict

        Returns:
            Email: Parsed email object
        """
        # Extract sender
        sender = ''
        if msg.get('from') and msg['from'].get('emailAddress'):
            sender = msg['from']['emailAddress'].get('address', '')

        # Extract recipient (first one)
        recipient = ''
        if msg.get('toRecipients') and len(msg['toRecipients']) > 0:
            recipient = msg['toRecipients'][0]['emailAddress'].get('address', '')

        # Extract and parse body
        body_plain, body_html = self._extract_body(msg)

        # Parse date (ISO 8601 format)
        date_str = msg.get('receivedDateTime', '')
        email_date = self._parse_date(date_str)

        # Categories (similar to Gmail labels)
        categories = msg.get('categories', [])

        return Email(
            id=msg.get('id', ''),
            thread_id=msg.get('conversationId', ''),
            sender=sender,
            recipient=recipient,
            subject=msg.get('subject', ''),
            body=body_plain or '',
            html_body=body_html,
            date=email_date,
            labels=categories,
            account_email=self.account_email
        )

    def _extract_body(self, msg: dict) -> tuple:
        """Extract plain and HTML body from message.

        Args:
            msg: Graph API message dict

        Returns:
            tuple: (plain_text_body, html_body)
        """
        body = msg.get('body', {})
        content_type = body.get('contentType', 'text')
        content = body.get('content', '')

        if content_type.lower() == 'html':
            # HTML body
            html_body = content
            # Convert to plain text
            plain_text = self._html_to_text(content)
            return plain_text, html_body
        else:
            # Plain text body
            return content, None

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
            logger.warning(f"Failed to parse HTML with lxml: {e}")
            # Fallback: try html.parser
            try:
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text(separator='\n', strip=True)
            except Exception:
                return html  # Return raw HTML as last resort

    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO 8601 date from Graph API.

        Args:
            date_str: ISO 8601 date (e.g., "2025-12-12T10:30:00Z")

        Returns:
            datetime: Parsed datetime object
        """
        try:
            # Graph API returns ISO 8601 format
            # Replace 'Z' with '+00:00' for proper parsing
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return datetime.now()

    def _translate_query(self, query: str) -> str:
        """Translate Gmail-style query to Graph API OData filter.

        Args:
            query: Gmail query (e.g., "newer_than:30d")

        Returns:
            str: Graph API $filter expression
        """
        # Handle newer_than query
        if query.startswith('newer_than:'):
            days_str = query.replace('newer_than:', '').replace('d', '')
            try:
                days = int(days_str)
                cutoff_date = datetime.now() - timedelta(days=days)
                # Format in ISO 8601
                date_iso = cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                return f"receivedDateTime ge {date_iso}"
            except ValueError:
                logger.warning(f"Invalid newer_than query: {query}")
                return ''

        # Handle from: query
        if query.startswith('from:'):
            sender = query.replace('from:', '').strip()
            return f"from/emailAddress/address eq '{sender}'"

        # Handle subject: query
        if query.startswith('subject:'):
            subject_text = query.replace('subject:', '').strip()
            return f"contains(subject, '{subject_text}')"

        # Default: return as-is (might be already OData format)
        logger.debug(f"Query translation not implemented for: {query}")
        return query

    def _load_token(self) -> Optional[dict]:
        """Load token from file.

        Returns:
            Optional[dict]: Token data or None if not found
        """
        if not self.token_path.exists():
            return None

        try:
            with open(self.token_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load token: {e}")
            return None

    def _save_token(self, token_data: dict):
        """Save token to file.

        Args:
            token_data: Token dict to save
        """
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'wb') as f:
                pickle.dump(token_data, f)
            logger.debug(f"Token saved for {self.account_email}")
        except Exception as e:
            logger.error(f"Failed to save token: {e}")

    def _is_token_expired(self, token_data: dict) -> bool:
        """Check if access token is expired.

        Args:
            token_data: Token dict with expires_in and acquired_at

        Returns:
            bool: True if token is expired or will expire soon
        """
        if 'expires_in' not in token_data or 'acquired_at' not in token_data:
            return True

        acquired_at = token_data['acquired_at']
        expires_in = token_data['expires_in']

        # Check if expired (with 5-minute buffer)
        expiration_time = acquired_at + expires_in - 300
        return time.time() > expiration_time

    def _refresh_token(self, token_data: dict) -> Optional[dict]:
        """Refresh access token using refresh token.

        Args:
            token_data: Token dict with refresh_token

        Returns:
            Optional[dict]: New token data or None if refresh failed
        """
        if 'refresh_token' not in token_data:
            return None

        try:
            result = self.app.acquire_token_by_refresh_token(
                token_data['refresh_token'],
                scopes=self.scopes
            )

            if 'access_token' in result:
                # Add timestamp
                result['acquired_at'] = time.time()
                logger.debug("Token refreshed successfully")
                return result
            else:
                error = result.get('error_description', 'Unknown error')
                logger.error(f"Token refresh failed: {error}")
                return None

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
