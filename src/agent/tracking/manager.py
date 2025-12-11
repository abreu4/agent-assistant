"""Job tracking manager - orchestrates email sync, detection, and database storage."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..email import get_account_manager, GmailProvider, JobDetector, get_email_rag
from .database import get_job_database

logger = logging.getLogger(__name__)


class JobManager:
    """Orchestrates the full job tracking pipeline.

    Pipeline:
    1. Fetch emails from all configured accounts
    2. Detect job aggregator emails
    3. Extract job postings using LLM
    4. Index jobs in Email RAG
    5. Store jobs in SQLite database
    """

    def __init__(self):
        """Initialize job manager with all required components."""
        self.account_manager = get_account_manager()
        self.job_detector = JobDetector()
        self.email_rag = get_email_rag()
        self.database = get_job_database()

        logger.info("JobManager initialized")

    def sync_emails(
        self,
        account_email: Optional[str] = None,
        max_emails: int = 100,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync emails and extract job postings.

        This is the main pipeline method that:
        1. Fetches emails from Gmail
        2. Detects job aggregator emails
        3. Extracts jobs using LLM
        4. Indexes jobs in RAG
        5. Stores jobs in database

        Args:
            account_email: Specific account to sync, or None for current account
            max_emails: Maximum emails to fetch
            query: Gmail search query (default: from config)

        Returns:
            Dict with sync statistics:
                - emails_fetched: Total emails fetched
                - aggregators_found: Job aggregator emails detected
                - jobs_extracted: Total jobs extracted from aggregators
                - jobs_stored: New jobs stored in database (excludes duplicates)
                - jobs_indexed: Jobs indexed in RAG
                - account: Email account synced
        """
        stats = {
            'emails_fetched': 0,
            'aggregators_found': 0,
            'jobs_extracted': 0,
            'jobs_stored': 0,
            'jobs_indexed': 0,
            'account': None,
            'errors': []
        }

        try:
            # Get account to sync
            if account_email:
                accounts = self.account_manager.get_accounts()
                account = next((a for a in accounts if a.email == account_email), None)
                if not account:
                    logger.error(f"Account {account_email} not found")
                    stats['errors'].append(f"Account {account_email} not found")
                    return stats
            else:
                account = self.account_manager.get_current_account()
                if not account:
                    logger.error("No current account set")
                    stats['errors'].append("No current account configured")
                    return stats

            stats['account'] = account.email
            logger.info(f"Starting email sync for {account.email}")

            # Step 1: Fetch emails
            provider = GmailProvider(account.email)
            if not provider.authenticate():
                logger.error(f"Failed to authenticate {account.email}")
                stats['errors'].append(f"Authentication failed for {account.email}")
                return stats

            emails = provider.fetch_emails(max_results=max_emails, query=query)
            stats['emails_fetched'] = len(emails)
            logger.info(f"Fetched {len(emails)} emails from {account.email}")

            if not emails:
                logger.info("No emails to process")
                return stats

            # Step 2: Detect job aggregators
            aggregator_emails = []
            for email in emails:
                if self.job_detector.is_aggregator_email(email):
                    aggregator_emails.append(email)

            stats['aggregators_found'] = len(aggregator_emails)
            logger.info(f"Found {len(aggregator_emails)} job aggregator emails")

            if not aggregator_emails:
                logger.info("No job aggregator emails found")
                return stats

            # Step 3 & 4: Extract jobs and store in database
            all_jobs = []
            for email in aggregator_emails:
                try:
                    # Extract jobs using LLM
                    jobs = self.job_detector.parse_jobs(email)
                    logger.info(f"Extracted {len(jobs)} jobs from email {email.id}")

                    # Store each job in database
                    for job in jobs:
                        # Create unique email_id for each job
                        job_email_id = f"{email.id}_{job.position}_{job.company}"

                        # Add to database
                        job_id = self.database.add_job(
                            email_id=job_email_id,
                            account_email=account.email,
                            position=job.position,
                            company=job.company,
                            location=job.location,
                            salary=job.salary,
                            job_type=job.job_type,
                            description=job.description,
                            application_link=job.link,
                            email_date=email.date
                        )

                        if job_id:
                            stats['jobs_stored'] += 1
                            all_jobs.append(job)
                        # else: duplicate, already in database

                    stats['jobs_extracted'] += len(jobs)

                except Exception as e:
                    logger.error(f"Error processing email {email.id}: {e}")
                    stats['errors'].append(f"Error processing email {email.id}: {str(e)}")

            # Step 5: Index in RAG (using EmailRAG's job indexing)
            try:
                if aggregator_emails:
                    logger.info(f"Indexing {len(aggregator_emails)} aggregator emails in RAG")
                    self.email_rag.index_jobs(
                        emails=aggregator_emails,
                        account_email=account.email
                    )
                    stats['jobs_indexed'] = len(all_jobs)
            except Exception as e:
                logger.error(f"Error indexing jobs in RAG: {e}")
                stats['errors'].append(f"RAG indexing error: {str(e)}")

            # Update last sync time
            self.account_manager.update_last_sync(account.email)

            logger.info(
                f"Sync complete: {stats['emails_fetched']} emails, "
                f"{stats['aggregators_found']} aggregators, "
                f"{stats['jobs_extracted']} jobs extracted, "
                f"{stats['jobs_stored']} new jobs stored"
            )

            return stats

        except Exception as e:
            logger.error(f"Email sync failed: {e}")
            stats['errors'].append(f"Sync failed: {str(e)}")
            return stats

    def get_jobs(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        account_email: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query jobs from database.

        Args:
            status: Filter by status (e.g., "new", "applied", "interviewing")
            company: Filter by company name (partial match)
            account_email: Filter by source email account
            limit: Maximum number of results
            offset: Skip first N results

        Returns:
            List[Dict]: List of job records
        """
        return self.database.get_jobs(
            status=status,
            company=company,
            account_email=account_email,
            limit=limit,
            offset=offset
        )

    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID.

        Args:
            job_id: Job database ID

        Returns:
            Optional[Dict]: Job record or None if not found
        """
        return self.database.get_job_by_id(job_id)

    def update_job_status(
        self,
        job_id: int,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """Update job application status.

        Args:
            job_id: Job database ID
            status: New status (e.g., "interested", "applied", "interviewing", "rejected", "archived")
            notes: Optional notes about the update

        Returns:
            bool: True if updated successfully
        """
        return self.database.update_job_status(job_id, status, notes)

    def delete_job(self, job_id: int) -> bool:
        """Delete a job from tracking.

        Args:
            job_id: Job database ID

        Returns:
            bool: True if deleted successfully
        """
        return self.database.delete_job(job_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get job tracking statistics.

        Returns:
            Dict: Statistics including:
                - total: Total jobs tracked
                - by_status: Count by status
                - recent_7_days: Jobs found in last 7 days
                - by_account: Count by email account
                - top_companies: Top 10 companies by job count
        """
        return self.database.get_stats()

    def search_jobs(
        self,
        query: str,
        company: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Semantic search for jobs using RAG.

        Args:
            query: Search query (e.g., "python developer", "machine learning")
            company: Filter by company name
            location: Filter by location
            limit: Maximum results to return

        Returns:
            List[Dict]: Relevant jobs with metadata
        """
        try:
            # Use EmailRAG to search
            results = self.email_rag.search(
                query=query,
                limit=limit,
                company=company,
                location=location
            )

            # Enrich with database info (status, notes)
            enriched_results = []
            for result in results:
                # Get email_id from metadata
                email_id = result.get('email_id')
                if email_id:
                    # Look up in database
                    db_job = self.database.get_job_by_email_id(email_id)
                    if db_job:
                        result['db_status'] = db_job['status']
                        result['db_notes'] = db_job['notes']
                        result['db_id'] = db_job['id']

                enriched_results.append(result)

            return enriched_results

        except Exception as e:
            logger.error(f"Job search failed: {e}")
            return []


# Singleton instance
_job_manager = None


def get_job_manager() -> JobManager:
    """Get singleton JobManager instance.

    Returns:
        JobManager: Global manager instance
    """
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
