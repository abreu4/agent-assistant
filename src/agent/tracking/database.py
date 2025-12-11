"""SQLite database for job application tracking."""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ...utils.config import config

logger = logging.getLogger(__name__)


class JobDatabase:
    """Manages SQLite database for tracking job postings."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize job database.

        Args:
            db_path: Path to SQLite database file. Defaults to config setting or ~/.job_agent/jobs.db
        """
        if db_path is None:
            # Get from config or use default
            db_path_str = config.get('job_agent.tracking.database_path', '~/.job_agent/jobs.db')
            db_path = Path(db_path_str).expanduser()

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = None
        self._initialize_database()

    def _initialize_database(self):
        """Create database schema if it doesn't exist."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return dicts instead of tuples

        cursor = self.conn.cursor()

        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT UNIQUE NOT NULL,
                account_email TEXT NOT NULL,
                company TEXT,
                position TEXT NOT NULL,
                location TEXT,
                salary TEXT,
                job_type TEXT,
                description TEXT,
                application_link TEXT,
                found_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                email_date TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'new',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_company
            ON jobs(company)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_found_date
            ON jobs(found_date DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_account
            ON jobs(account_email)
        """)

        self.conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def add_job(
        self,
        email_id: str,
        account_email: str,
        position: str,
        company: Optional[str] = None,
        location: Optional[str] = None,
        salary: Optional[str] = None,
        job_type: Optional[str] = None,
        description: Optional[str] = None,
        application_link: Optional[str] = None,
        email_date: Optional[datetime] = None
    ) -> Optional[int]:
        """Add a new job posting to the database.

        Args:
            email_id: Unique email ID (prevents duplicates)
            account_email: Source email account
            position: Job position/title
            company: Company name
            location: Job location
            salary: Salary information
            job_type: e.g., "full-time", "contract", "remote"
            description: Job description
            application_link: URL to apply
            email_date: When the email was received

        Returns:
            int: Job ID if successful, None if duplicate or error
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT INTO jobs (
                    email_id, account_email, company, position, location,
                    salary, job_type, description, application_link, email_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_id, account_email, company, position, location,
                salary, job_type, description, application_link, email_date
            ))

            self.conn.commit()
            job_id = cursor.lastrowid
            logger.info(f"Added job {job_id}: {position} at {company}")
            return job_id

        except sqlite3.IntegrityError:
            logger.debug(f"Job from email {email_id} already exists")
            return None
        except Exception as e:
            logger.error(f"Failed to add job: {e}")
            return None

    def get_jobs(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        account_email: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query jobs from database with filters.

        Args:
            status: Filter by status (e.g., "new", "applied", "interviewing")
            company: Filter by company name (partial match)
            account_email: Filter by source email account
            limit: Maximum number of results
            offset: Skip first N results

        Returns:
            List[Dict]: List of job records as dictionaries
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT * FROM jobs WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if company:
                query += " AND company LIKE ?"
                params.append(f"%{company}%")

            if account_email:
                query += " AND account_email = ?"
                params.append(account_email)

            query += " ORDER BY found_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to query jobs: {e}")
            return []

    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID.

        Args:
            job_id: Job database ID

        Returns:
            Optional[Dict]: Job record or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def get_job_by_email_id(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by its source email ID.

        Args:
            email_id: Email ID that contained the job

        Returns:
            Optional[Dict]: Job record or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE email_id = ?", (email_id,))
            row = cursor.fetchone()

            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get job by email_id {email_id}: {e}")
            return None

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
        try:
            cursor = self.conn.cursor()

            if notes:
                cursor.execute("""
                    UPDATE jobs
                    SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, notes, job_id))
            else:
                cursor.execute("""
                    UPDATE jobs
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, job_id))

            self.conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Updated job {job_id} status to '{status}'")
                return True
            else:
                logger.warning(f"Job {job_id} not found")
                return False

        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False

    def delete_job(self, job_id: int) -> bool:
        """Delete a job from the database.

        Args:
            job_id: Job database ID

        Returns:
            bool: True if deleted successfully
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self.conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Deleted job {job_id}")
                return True
            else:
                logger.warning(f"Job {job_id} not found")
                return False

        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dict: Statistics including total jobs, jobs by status, etc.
        """
        try:
            cursor = self.conn.cursor()

            # Total jobs
            cursor.execute("SELECT COUNT(*) as total FROM jobs")
            total = cursor.fetchone()['total']

            # Jobs by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
                ORDER BY count DESC
            """)
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # Recent jobs (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) as recent
                FROM jobs
                WHERE found_date >= datetime('now', '-7 days')
            """)
            recent = cursor.fetchone()['recent']

            # Jobs by account
            cursor.execute("""
                SELECT account_email, COUNT(*) as count
                FROM jobs
                GROUP BY account_email
                ORDER BY count DESC
            """)
            by_account = {row['account_email']: row['count'] for row in cursor.fetchall()}

            # Top companies
            cursor.execute("""
                SELECT company, COUNT(*) as count
                FROM jobs
                WHERE company IS NOT NULL
                GROUP BY company
                ORDER BY count DESC
                LIMIT 10
            """)
            top_companies = [(row['company'], row['count']) for row in cursor.fetchall()]

            return {
                'total': total,
                'by_status': by_status,
                'recent_7_days': recent,
                'by_account': by_account,
                'top_companies': top_companies
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                'total': 0,
                'by_status': {},
                'recent_7_days': 0,
                'by_account': {},
                'top_companies': []
            }

    def clear_all(self) -> bool:
        """Clear all jobs from the database.

        WARNING: This deletes all job records permanently.

        Returns:
            bool: True if cleared successfully
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM jobs")
            self.conn.commit()
            logger.warning(f"Cleared all jobs from database ({cursor.rowcount} rows)")
            return True

        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")

    def __del__(self):
        """Cleanup on deletion."""
        self.close()


# Singleton instance
_job_database = None


def get_job_database() -> JobDatabase:
    """Get singleton JobDatabase instance.

    Returns:
        JobDatabase: Global database instance
    """
    global _job_database
    if _job_database is None:
        _job_database = JobDatabase()
    return _job_database
