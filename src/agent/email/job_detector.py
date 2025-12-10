"""LLM-based job posting detection and extraction."""

import re
import json
from typing import List, Optional

from pydantic import BaseModel, Field

from .provider import Email
from src.agent.llm_system import HybridLLMSystem
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobPosting(BaseModel):
    """Individual job posting extracted by LLM.

    Attributes:
        email_id: Source email ID (added after extraction)
        account_email: Source account email (for multi-account support)
        position: Job title/position name
        company: Company name
        location: Job location (city, state, or 'Remote')
        link: URL to job posting or application
        description: Brief job description
        salary: Salary range if mentioned
        job_type: Full-time, Part-time, Contract, etc.
        raw_text: Original text block for this job
    """
    email_id: str = ""  # Set after extraction
    account_email: str = ""  # Set after extraction (track source account)
    position: str = Field(description="Job title/position name")
    company: Optional[str] = Field(default=None, description="Company name")
    location: Optional[str] = Field(default=None, description="Job location (city, state, or 'Remote')")
    link: Optional[str] = Field(default=None, description="URL to job posting or application")
    description: Optional[str] = Field(default=None, description="Brief job description (1-2 sentences)")
    salary: Optional[str] = Field(default=None, description="Salary range if mentioned")
    job_type: Optional[str] = Field(default=None, description="Full-time, Part-time, Contract, etc.")
    raw_text: str = ""  # Set during parsing


class JobDetector:
    """Detect aggregator emails and extract job postings using LLM.

    Uses a two-phase approach:
    1. Simple sender pattern detection (heuristic - fast filter)
    2. LLM-based semantic extraction (flexible - handles any format)
    """

    # Simple aggregator detection (low-level heuristic)
    AGGREGATOR_PATTERNS = [
        r'@linkedin\.com$',
        r'@indeed\.com$',
        r'@glassdoor\.com$',
        r'@ziprecruiter\.com$',
        r'^jobs@',
        r'^alerts@',
        r'^jobalerts',
        r'^career.*alerts',
        r'^noreply.*jobs',
        r'^recruiting@',
        r'^talent@',
    ]

    def __init__(self, llm_system: Optional[HybridLLMSystem] = None):
        """Initialize job detector with LLM system.

        Args:
            llm_system: LLM system for semantic extraction (uses default if None)
        """
        self.llm_system = llm_system or HybridLLMSystem()

    def is_aggregator_email(self, email: Email) -> bool:
        """Quick check if email is from job aggregator.

        Uses simple sender pattern matching for fast filtering.

        Args:
            email: Email to check

        Returns:
            bool: True if likely from job aggregator
        """
        sender_lower = email.sender.lower()
        for pattern in self.AGGREGATOR_PATTERNS:
            if re.search(pattern, sender_lower):
                logger.debug(f"Aggregator email detected: {email.sender}")
                return True
        return False

    def parse_jobs(self, email: Email) -> List[JobPosting]:
        """Extract job postings from email using LLM.

        Uses local LLM to semantically extract structured job data from
        aggregator emails. Handles varying formats automatically.

        Args:
            email: Email to parse

        Returns:
            List[JobPosting]: Extracted job postings (empty if none found)
        """
        if not self.is_aggregator_email(email):
            logger.debug(f"Not an aggregator email: {email.sender}")
            return []

        try:
            # Use local LLM for extraction (fast, free, semantic)
            local_llm = self.llm_system.get_model('local')

            # Prepare prompt for LLM
            system_prompt = """You are a job posting extraction assistant.
Extract individual job postings from the email body below.

For each job, extract:
- position: The job title
- company: Company name (if mentioned)
- location: Location (city/state or "Remote")
- link: Any URL for applying or more info
- description: Brief summary (1-2 sentences max, optional)
- salary: Salary range if mentioned
- job_type: Full-time, Part-time, Contract, etc. (if mentioned)

Return a JSON array of job postings. Each job should be a JSON object.
If no clear jobs found, return an empty array: []

Example output format:
[
  {
    "position": "Senior Python Developer",
    "company": "Acme Corp",
    "location": "Remote",
    "link": "https://acme.com/jobs/123",
    "description": "Looking for senior developer with 5+ years experience",
    "salary": "$120k-$150k",
    "job_type": "Full-time"
  }
]

IMPORTANT: Return ONLY valid JSON. No markdown, no explanations, just the JSON array."""

            user_prompt = f"Email subject: {email.subject}\n\nEmail body:\n{email.body[:5000]}"

            # Get LLM response
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = local_llm.invoke(messages)
            response_text = response.content.strip()

            # Parse JSON response
            jobs_data = self._parse_json_response(response_text)

            if not jobs_data:
                logger.info(f"No jobs extracted from email: {email.subject}")
                return []

            # Convert to JobPosting objects
            jobs = []
            for job_dict in jobs_data:
                try:
                    job = JobPosting(**job_dict)
                    job.email_id = email.id  # Add email ID reference
                    # Store original text (approximation)
                    job.raw_text = f"{job.position} at {job.company or 'Unknown'}"
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to create JobPosting from dict: {e}")
                    continue

            logger.info(f"✓ LLM extracted {len(jobs)} jobs from email: {email.subject}")
            return jobs

        except Exception as e:
            logger.error(f"Failed to parse jobs with LLM: {e}")
            logger.debug(f"Email subject: {email.subject}")
            logger.debug(f"Email body preview: {email.body[:500]}")
            return []

    def _parse_json_response(self, response_text: str) -> List[dict]:
        """Parse JSON response from LLM, handling common formatting issues.

        Args:
            response_text: LLM response text

        Returns:
            List[dict]: Parsed job data (empty list if parsing fails)
        """
        # Remove markdown code blocks if present
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        response_text = response_text.strip()

        try:
            # Parse JSON
            jobs_data = json.loads(response_text)

            # Handle single job (not in array)
            if isinstance(jobs_data, dict):
                jobs_data = [jobs_data]

            # Validate it's a list
            if not isinstance(jobs_data, list):
                logger.warning(f"LLM returned non-list response: {type(jobs_data)}")
                return []

            return jobs_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return []
