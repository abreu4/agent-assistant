"""Email retrieval-augmented generation system for job postings."""

import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from .gmail_provider import GmailProvider
from .job_detector import JobDetector, JobPosting
from .account_manager import get_account_manager
from src.agent.custom_embeddings import DirectOllamaEmbeddings
from src.utils.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailRAG:
    """Email retrieval-augmented generation system with multi-account support.

    Indexes individual job postings from aggregator emails and provides
    semantic search capabilities. Each job becomes a separate document
    for precise relevance matching against user profile.

    Supports multiple Gmail accounts with per-account indexing.
    """

    def __init__(self):
        """Initialize email RAG system with multi-account support."""
        # Account manager
        self.account_manager = get_account_manager()

        # Job detector (LLM-based)
        self.detector = JobDetector()

        # Base index directory (per-account subdirs created on demand)
        self.base_index_dir = Path(
            config.get('job_agent.email.email_index_path', '~/.job_agent/email_index')
        ).expanduser()
        self.base_index_dir.mkdir(parents=True, exist_ok=True)

        # Per-account lazy-loaded components
        self.providers = {}  # account_email -> GmailProvider
        self.vectorstores = {}  # account_email -> Chroma
        self.embeddings = None  # Shared across all accounts

        # Track indexed jobs per account (account_email -> {job_key -> hash})
        self.indexed_jobs = {}

        logger.info(f"Email RAG initialized (base index: {self.base_index_dir})")

    def _get_embeddings(self) -> DirectOllamaEmbeddings:
        """Get or create embeddings instance.

        Uses DirectOllamaEmbeddings with nomic-embed-text model
        (same as workspace RAG for consistency). Shared across all accounts.

        Returns:
            DirectOllamaEmbeddings: Embeddings instance
        """
        if self.embeddings is None:
            self.embeddings = DirectOllamaEmbeddings()
            logger.info("Created DirectOllamaEmbeddings instance")
        return self.embeddings

    def _get_provider(self, account_email: str) -> GmailProvider:
        """Get or create Gmail provider for account.

        Args:
            account_email: Email address of account

        Returns:
            GmailProvider: Provider instance for account
        """
        if account_email not in self.providers:
            self.providers[account_email] = GmailProvider(account_email)
            logger.debug(f"Created provider for {account_email}")
        return self.providers[account_email]

    def _get_index_dir(self, account_email: str) -> Path:
        """Get index directory for specific account.

        Args:
            account_email: Email address of account

        Returns:
            Path: Per-account index directory
        """
        # Sanitize email for filesystem (replace @ and . with safe chars)
        safe_email = account_email.replace('@', '_at_').replace('.', '_')
        account_dir = self.base_index_dir / safe_email
        account_dir.mkdir(parents=True, exist_ok=True)
        return account_dir

    def _get_vectorstore(self, account_email: str) -> Optional[Chroma]:
        """Get vectorstore for account (if exists).

        Args:
            account_email: Email address of account

        Returns:
            Optional[Chroma]: Vectorstore or None if not created yet
        """
        return self.vectorstores.get(account_email)

    def index_emails(
        self,
        account_email: Optional[str] = None,
        force_reindex: bool = False
    ) -> int:
        """Index individual job postings from aggregator emails.

        Fetches emails, detects aggregator emails, extracts jobs using LLM,
        and indexes each job as a separate document for semantic search.

        Args:
            account_email: Email address to index (None = all accounts)
            force_reindex: If True, re-index all jobs even if already indexed

        Returns:
            int: Number of new jobs indexed
        """
        # Determine which accounts to index
        if account_email:
            accounts_to_index = [account_email]
        else:
            # Index all configured accounts
            accounts = self.account_manager.get_accounts()
            if not accounts:
                logger.warning("No accounts configured")
                return 0
            accounts_to_index = [acc.email for acc in accounts]

        logger.info(f"Starting email indexing for {len(accounts_to_index)} account(s)...")

        total_indexed = 0
        for acc_email in accounts_to_index:
            indexed_count = self._index_account_emails(acc_email, force_reindex)
            total_indexed += indexed_count

        logger.info(f"✓ Indexed total of {total_indexed} job postings across {len(accounts_to_index)} account(s)")
        return total_indexed

    def _index_account_emails(self, account_email: str, force_reindex: bool) -> int:
        """Index emails for a specific account.

        Args:
            account_email: Email address to index
            force_reindex: If True, re-index all jobs even if already indexed

        Returns:
            int: Number of new jobs indexed for this account
        """
        logger.info(f"Indexing emails for account: {account_email}")

        # Get provider for this account
        provider = self._get_provider(account_email)

        # Authenticate with email provider
        if not provider.is_authenticated():
            logger.info(f"Authenticating {account_email}...")
            if not provider.authenticate():
                logger.error(f"Failed to authenticate {account_email}")
                return 0

        # Fetch emails
        max_emails = config.get('job_agent.email.max_emails_per_sync', 100)
        emails = provider.fetch_emails(max_results=max_emails)

        if not emails:
            logger.info(f"No emails to index for {account_email}")
            return 0

        logger.info(f"Fetched {len(emails)} emails from {account_email}, parsing jobs...")

        # Parse jobs from aggregator emails
        all_jobs = []
        for email in emails:
            jobs = self.detector.parse_jobs(email)
            all_jobs.extend(jobs)

        logger.info(f"Parsed {len(all_jobs)} jobs from {len(emails)} emails ({account_email})")

        if not all_jobs:
            logger.info(f"No job postings found in emails for {account_email}")
            return 0

        # Initialize tracked jobs for this account if needed
        if account_email not in self.indexed_jobs:
            self.indexed_jobs[account_email] = {}

        # Convert jobs to documents
        documents = []
        for job in all_jobs:
            job_hash = self._get_job_hash(job)
            job_key = f"{job.email_id}:{job.position}"

            # Skip if already indexed (unless force)
            if not force_reindex and job_key in self.indexed_jobs[account_email]:
                if self.indexed_jobs[account_email][job_key] == job_hash:
                    logger.debug(f"Skipping already indexed job: {job.position}")
                    continue

            # Convert job to document (ONE job = ONE document)
            doc = self._job_to_document(job)
            documents.append(doc)
            self.indexed_jobs[account_email][job_key] = job_hash

        if not documents:
            logger.info(f"All jobs already indexed for {account_email}")
            return 0

        # Index with Chroma (per-account vectorstore)
        embeddings = self._get_embeddings()
        index_dir = self._get_index_dir(account_email)

        if account_email not in self.vectorstores:
            # Create new vectorstore for this account
            logger.info(f"Creating new Chroma vectorstore for {account_email}...")
            self.vectorstores[account_email] = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=str(index_dir),
                collection_name="jobs"  # Collection for job postings
            )
        else:
            # Add to existing vectorstore
            logger.info(f"Adding {len(documents)} documents to {account_email} vectorstore...")
            self.vectorstores[account_email].add_documents(documents)

        logger.info(f"✓ Indexed {len(documents)} job postings for {account_email}")
        return len(documents)

    def _job_to_document(self, job: JobPosting) -> Document:
        """Convert JobPosting to LangChain document.

        CRITICAL: Each job becomes ONE document (not chunked).
        This allows semantic search to return individual jobs.

        Args:
            job: JobPosting to convert

        Returns:
            Document: LangChain document with job content and metadata
        """
        # Create searchable content (what gets embedded)
        content_parts = [f"Position: {job.position}"]

        if job.company:
            content_parts.append(f"Company: {job.company}")
        if job.location:
            content_parts.append(f"Location: {job.location}")
        if job.description:
            content_parts.append(f"Description: {job.description}")
        if job.salary:
            content_parts.append(f"Salary: {job.salary}")
        if job.job_type:
            content_parts.append(f"Type: {job.job_type}")

        searchable_content = "\n".join(content_parts)

        # Create document with full metadata (including account_email)
        doc = Document(
            page_content=searchable_content,
            metadata={
                'email_id': job.email_id,
                'account_email': job.account_email,  # Track source account
                'position': job.position,
                'company': job.company or 'Unknown',
                'location': job.location or 'Not specified',
                'link': job.link or '',
                'salary': job.salary or 'Not specified',
                'job_type': job.job_type or 'Not specified',
                'description': job.description or '',
            }
        )

        return doc

    def _get_job_hash(self, job: JobPosting) -> str:
        """Get hash of job posting for change detection.

        Args:
            job: JobPosting to hash

        Returns:
            str: MD5 hash of job content
        """
        content = f"{job.email_id}:{job.position}:{job.company}"
        return hashlib.md5(content.encode()).hexdigest()

    def search(
        self,
        query: str,
        k: int = 10,
        account_email: Optional[str] = None,
        filter_company: Optional[str] = None,
        filter_location: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """Search job postings semantically across accounts.

        Args:
            query: Search query (can be from user's CV for similarity matching)
            k: Number of results to return
            account_email: Search specific account (None = all accounts)
            filter_company: Filter by company name
            filter_location: Filter by location

        Returns:
            List[Tuple[Document, float]]: List of (Document, similarity_score) tuples
        """
        # Determine which accounts to search
        if account_email:
            accounts_to_search = [account_email]
        else:
            # Search all accounts with vectorstores
            accounts_to_search = list(self.vectorstores.keys())

        if not accounts_to_search:
            logger.warning("No vectorstores available, returning empty results")
            return []

        # Build filter dict
        filter_dict = {}
        if filter_company:
            filter_dict['company'] = filter_company
        if filter_location:
            filter_dict['location'] = filter_location

        all_results = []

        try:
            # Search each account's vectorstore
            for acc_email in accounts_to_search:
                vectorstore = self.vectorstores.get(acc_email)
                if vectorstore is None:
                    logger.debug(f"No vectorstore for {acc_email}, skipping")
                    continue

                # Search this account (returns jobs ranked by semantic similarity)
                results = vectorstore.similarity_search_with_score(
                    query,
                    k=k,  # Get top k from each account
                    filter=filter_dict if filter_dict else None
                )

                all_results.extend(results)

            # Sort merged results by score (lower is better for distance)
            all_results.sort(key=lambda x: x[1])

            # Return top k from merged results
            final_results = all_results[:k]

            logger.debug(f"Search returned {len(final_results)} results from {len(accounts_to_search)} account(s)")
            return final_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def find_relevant_jobs_for_profile(
        self,
        profile_text: str,
        k: int = 20,
        account_email: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """Find jobs semantically similar to user's complete profile.

        This is the key method for relevance ranking:
        - Embeds the profile text using same embeddings (nomic-embed-text)
        - Profile = ALL user documents: CV + cover letters + motivations + preferences
        - Finds jobs with similar embeddings (skills + values + goals)
        - Returns top K most relevant jobs across all accounts (or specific account)

        Args:
            profile_text: Combined text from ALL user documents (from document RAG)
                         - CV: Skills, experience, education
                         - Cover letters: Interests, targeted companies
                         - Motivations: Career goals, values, work style
                         - Preferences: Company culture, location, etc.
            k: Number of relevant jobs to return
            account_email: Search specific account (None = all accounts)

        Returns:
            List[Tuple[Document, float]]: Sorted by relevance (job_document, similarity_score)
        """
        logger.info(f"Finding {k} relevant jobs for user profile...")
        return self.search(query=profile_text, k=k, account_email=account_email)

    def get_job_summary(self) -> str:
        """Get summary of indexed jobs across all accounts.

        Returns:
            str: Human-readable summary of indexed jobs per account
        """
        if not self.vectorstores:
            return "No jobs indexed yet"

        try:
            summary_parts = []
            total_count = 0

            for acc_email, vectorstore in self.vectorstores.items():
                # Get collection stats for this account
                collection = vectorstore._collection
                count = collection.count()
                total_count += count
                summary_parts.append(f"  - {acc_email}: {count} jobs")

            summary = f"Indexed {total_count} total job postings:\n" + "\n".join(summary_parts)
            return summary

        except Exception as e:
            logger.error(f"Failed to get job summary: {e}")
            return "Unable to retrieve job summary"

    def clear_index(self, account_email: Optional[str] = None) -> bool:
        """Clear indexed jobs for specific account or all accounts.

        Args:
            account_email: Account to clear (None = all accounts)

        Returns:
            bool: True if successful
        """
        try:
            if account_email:
                # Clear specific account
                if account_email in self.vectorstores:
                    self.vectorstores[account_email].delete_collection()
                    del self.vectorstores[account_email]
                if account_email in self.indexed_jobs:
                    del self.indexed_jobs[account_email]
                logger.info(f"✓ Cleared indexed jobs for {account_email}")
            else:
                # Clear all accounts
                for vectorstore in self.vectorstores.values():
                    vectorstore.delete_collection()
                self.vectorstores = {}
                self.indexed_jobs = {}
                logger.info("✓ Cleared all indexed jobs")

            return True

        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
            return False


# Singleton pattern
_email_rag: Optional[EmailRAG] = None


def get_email_rag() -> EmailRAG:
    """Get or create global email RAG instance.

    Returns:
        EmailRAG: Singleton email RAG instance
    """
    global _email_rag
    if _email_rag is None:
        _email_rag = EmailRAG()
    return _email_rag
