"""Email infrastructure for job agent."""

from .provider import EmailProvider, Email
from .gmail_provider import GmailProvider
from .email_rag import EmailRAG, get_email_rag
from .job_detector import JobDetector, JobPosting
from .account_manager import AccountManager, Account, get_account_manager

__all__ = [
    'EmailProvider',
    'Email',
    'GmailProvider',
    'EmailRAG',
    'get_email_rag',
    'JobDetector',
    'JobPosting',
    'AccountManager',
    'Account',
    'get_account_manager',
]
