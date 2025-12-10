"""Abstract email provider interface for job agent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Email:
    """Email data structure.

    Attributes:
        id: Unique email ID from provider
        thread_id: Thread/conversation ID
        sender: From email address
        recipient: To email address
        subject: Email subject line
        body: Plain text body content
        html_body: HTML body content (optional)
        date: Email sent/received date
        labels: Email labels/tags (e.g., Gmail labels)
        account_email: Email account this came from (for multi-account support)
        is_job_related: Whether email contains job postings (set by detector)
        job_metadata: Extracted job metadata (set by detector)
    """
    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    html_body: Optional[str]
    date: datetime
    labels: List[str]
    account_email: str = ""  # Track source account
    is_job_related: bool = False
    job_metadata: Optional[dict] = None


class EmailProvider(ABC):
    """Abstract base class for email providers.

    This interface allows the job agent to support multiple email providers
    (Gmail, Outlook, Yahoo, etc.) by implementing this common interface.
    """

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with email service.

        Performs authentication flow (OAuth2, password, etc.) and stores
        credentials for future use. Should handle token refresh automatically.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if provider is currently authenticated.

        Returns:
            bool: True if authenticated and ready to fetch emails
        """
        pass

    @abstractmethod
    def fetch_emails(
        self,
        max_results: int = 100,
        query: Optional[str] = None
    ) -> List[Email]:
        """Fetch emails from provider.

        Args:
            max_results: Maximum number of emails to fetch
            query: Provider-specific query filter (e.g., Gmail search syntax)

        Returns:
            List[Email]: List of email objects
        """
        pass

    @abstractmethod
    def get_email_by_id(self, email_id: str) -> Optional[Email]:
        """Fetch single email by ID.

        Args:
            email_id: Unique email identifier from provider

        Returns:
            Optional[Email]: Email object if found, None otherwise
        """
        pass
