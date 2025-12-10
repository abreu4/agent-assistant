"""Multi-account Gmail management system."""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Account:
    """Gmail account information.

    Attributes:
        email: Gmail email address
        display_name: User's display name from Google
        added_date: When account was added
        last_sync: Last time emails were synced (optional)
    """
    email: str
    display_name: str
    added_date: datetime
    last_sync: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'email': self.email,
            'display_name': self.display_name,
            'added_date': self.added_date.isoformat(),
            'last_sync': self.last_sync.isoformat() if self.last_sync else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        """Create Account from dict."""
        return cls(
            email=data['email'],
            display_name=data['display_name'],
            added_date=datetime.fromisoformat(data['added_date']),
            last_sync=datetime.fromisoformat(data['last_sync']) if data.get('last_sync') else None
        )


class AccountManager:
    """Manage multiple Gmail accounts.

    Handles account registration, token storage, and current account selection.
    Stores account registry in JSON and per-account tokens as pickle files.
    """

    def __init__(self):
        """Initialize account manager with directories and registry."""
        # Account storage directory
        self.accounts_dir = Path("~/.job_agent/accounts").expanduser()
        self.accounts_dir.mkdir(parents=True, exist_ok=True)

        # Registry file
        self.registry_path = Path("~/.job_agent/accounts.json").expanduser()

        # Account data
        self.accounts: List[Account] = []
        self.current_account: Optional[str] = None

        # Load existing accounts
        self._load_registry()

        logger.info(f"AccountManager initialized ({len(self.accounts)} accounts)")

    def has_accounts(self) -> bool:
        """Check if any accounts are configured.

        Returns:
            bool: True if at least one account exists
        """
        return len(self.accounts) > 0

    def get_accounts(self) -> List[Account]:
        """Get list of all configured accounts.

        Returns:
            List[Account]: All registered accounts
        """
        return self.accounts.copy()

    def get_current_account(self) -> Optional[Account]:
        """Get currently active account.

        Returns:
            Optional[Account]: Current account or None if no accounts
        """
        if not self.current_account:
            return None

        for account in self.accounts:
            if account.email == self.current_account:
                return account

        return None

    def set_current_account(self, email: str) -> bool:
        """Switch to different account.

        Args:
            email: Email address of account to switch to

        Returns:
            bool: True if switched successfully
        """
        # Check account exists
        account_exists = any(a.email == email for a in self.accounts)

        if not account_exists:
            logger.error(f"Account not found: {email}")
            return False

        self.current_account = email
        self._save_registry()

        logger.info(f"Switched to account: {email}")
        return True

    async def add_account_interactive(self) -> Account:
        """Add new account via interactive OAuth flow.

        Opens browser for Google authentication, retrieves user info,
        saves token, and adds to registry.

        Returns:
            Account: Newly added account

        Raises:
            Exception: If OAuth flow fails
        """
        # Import here to avoid circular dependency
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        # OAuth credentials from environment
        client_id = os.getenv('GMAIL_CLIENT_ID')
        client_secret = os.getenv('GMAIL_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError(
                "Gmail OAuth credentials not configured!\n"
                "Please set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in your .env file.\n"
                "Get credentials from: https://console.cloud.google.com"
            )

        EMBEDDED_CLIENT_CONFIG = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"]
            }
        }

        scopes = ['https://www.googleapis.com/auth/gmail.readonly']

        try:
            # Run OAuth flow
            logger.info("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_config(
                EMBEDDED_CLIENT_CONFIG,
                scopes
            )

            # This opens browser automatically
            creds = flow.run_local_server(port=0)

            # Get user info from Gmail API
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()

            email = profile['emailAddress']
            display_name = email.split('@')[0]  # Default to email username

            # Check if account already exists
            if any(a.email == email for a in self.accounts):
                logger.warning(f"Account already exists: {email}")
                # Update token and return existing
                self._save_token(email, creds)
                for account in self.accounts:
                    if account.email == email:
                        return account

            # Save token
            self._save_token(email, creds)

            # Create account record
            account = Account(
                email=email,
                display_name=display_name,
                added_date=datetime.now()
            )

            # Add to registry
            self.accounts.append(account)

            # Set as current if first account
            if len(self.accounts) == 1:
                self.current_account = email

            self._save_registry()

            logger.info(f"✓ Added account: {email}")
            return account

        except Exception as e:
            logger.error(f"Failed to add account: {e}")
            raise

    def remove_account(self, email: str) -> bool:
        """Remove account and delete token.

        Args:
            email: Email address of account to remove

        Returns:
            bool: True if removed successfully
        """
        # Find account
        account = None
        for a in self.accounts:
            if a.email == email:
                account = a
                break

        if not account:
            logger.error(f"Account not found: {email}")
            return False

        # Delete token file
        token_path = self.get_token_path(email)
        if token_path.exists():
            token_path.unlink()

        # Remove from list
        self.accounts.remove(account)

        # Update current account if needed
        if self.current_account == email:
            if self.accounts:
                self.current_account = self.accounts[0].email
            else:
                self.current_account = None

        self._save_registry()

        logger.info(f"Removed account: {email}")
        return True

    def get_token_path(self, email: str) -> Path:
        """Get path to token file for account.

        Args:
            email: Email address

        Returns:
            Path: Path to token file
        """
        # Sanitize email for filename
        safe_email = email.replace('@', '_at_').replace('.', '_')
        return self.accounts_dir / f"{safe_email}.token"

    def update_last_sync(self, email: str):
        """Update last sync time for account.

        Args:
            email: Email address of account
        """
        for account in self.accounts:
            if account.email == email:
                account.last_sync = datetime.now()
                self._save_registry()
                break

    def _load_registry(self):
        """Load accounts from registry file."""
        if not self.registry_path.exists():
            logger.debug("No existing account registry")
            return

        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)

            self.accounts = [Account.from_dict(a) for a in data.get('accounts', [])]
            self.current_account = data.get('current_account')

            logger.info(f"Loaded {len(self.accounts)} accounts from registry")

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            self.accounts = []
            self.current_account = None

    def _save_registry(self):
        """Save accounts to registry file."""
        try:
            data = {
                'accounts': [a.to_dict() for a in self.accounts],
                'current_account': self.current_account
            }

            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved registry ({len(self.accounts)} accounts)")

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _save_token(self, email: str, creds):
        """Save credentials token for account.

        Args:
            email: Email address
            creds: Credentials object to save
        """
        import pickle

        token_path = self.get_token_path(email)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        with open(token_path, 'wb') as f:
            pickle.dump(creds, f)

        logger.debug(f"Saved token for {email}")


# Singleton instance
_account_manager: Optional[AccountManager] = None


def get_account_manager() -> AccountManager:
    """Get or create global AccountManager instance.

    Returns:
        AccountManager: Singleton account manager
    """
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager
