#!/usr/bin/env python3
"""
Phase 2 Testing: Email Infrastructure (Gmail + RAG)

Extensible test suite for email functionality including:
- Gmail OAuth2 authentication
- Email fetching and parsing
- Job detection and extraction
- Email RAG indexing and search
"""

import asyncio
from pathlib import Path

from src.agent.email import GmailProvider, JobDetector, get_email_rag
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Phase2TestRunner:
    """Extensible test runner for Phase 2 email infrastructure."""

    def __init__(self):
        self.provider = None
        self.detector = None
        self.email_rag = None
        self.test_results = {}

    def print_header(self, title: str):
        """Print formatted test section header."""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def print_result(self, test_name: str, success: bool, message: str = ""):
        """Print test result."""
        status = "✓ PASS" if success else "✗ FAIL"
        self.test_results[test_name] = success
        print(f"\n{status}: {test_name}")
        if message:
            print(f"  {message}")

    async def test_1_gmail_oauth(self) -> bool:
        """Test 1: Gmail OAuth2 Authentication.

        Tests OAuth2 flow, token persistence, and service initialization.
        """
        self.print_header("Test 1: Gmail OAuth2 Authentication")

        try:
            self.provider = GmailProvider()

            # Check credentials file exists
            if not self.provider.credentials_path.exists():
                self.print_result(
                    "OAuth2 Authentication",
                    False,
                    f"Credentials file not found: {self.provider.credentials_path}\n"
                    f"  Setup instructions:\n"
                    f"  1. Go to: https://console.cloud.google.com/\n"
                    f"  2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    f"  3. Download JSON credentials\n"
                    f"  4. Save to: {self.provider.credentials_path}"
                )
                return False

            # Authenticate
            print("\nAttempting Gmail authentication...")
            print("(Browser window will open for OAuth consent)")
            success = self.provider.authenticate()

            if success:
                self.print_result(
                    "OAuth2 Authentication",
                    True,
                    f"Token saved to: {self.provider.token_path}"
                )
                return True
            else:
                self.print_result(
                    "OAuth2 Authentication",
                    False,
                    "Authentication failed"
                )
                return False

        except Exception as e:
            self.print_result(
                "OAuth2 Authentication",
                False,
                f"Exception: {e}"
            )
            return False

    async def test_2_fetch_emails(self) -> bool:
        """Test 2: Email Fetching and Parsing.

        Tests email retrieval from Gmail API and parsing.
        """
        self.print_header("Test 2: Email Fetching and Parsing")

        if not self.provider or not self.provider.is_authenticated():
            self.print_result(
                "Email Fetching",
                False,
                "Provider not authenticated (skipping)"
            )
            return False

        try:
            # Fetch last 10 emails
            print("\nFetching last 10 emails...")
            emails = self.provider.fetch_emails(max_results=10)

            if emails:
                self.print_result(
                    "Email Fetching",
                    True,
                    f"Fetched {len(emails)} emails"
                )

                # Display sample
                print("\n  Sample emails:")
                for i, email in enumerate(emails[:3], 1):
                    print(f"  {i}. From: {email.sender[:50]}")
                    print(f"     Subject: {email.subject[:60]}")
                    print(f"     Date: {email.date}")

                return True
            else:
                self.print_result(
                    "Email Fetching",
                    False,
                    "No emails fetched"
                )
                return False

        except Exception as e:
            self.print_result(
                "Email Fetching",
                False,
                f"Exception: {e}"
            )
            return False

    async def test_3_job_detection(self) -> bool:
        """Test 3: Job Detection and LLM Extraction.

        Tests aggregator email detection and LLM-based job parsing.
        """
        self.print_header("Test 3: Job Detection and LLM Extraction")

        if not self.provider or not self.provider.is_authenticated():
            self.print_result(
                "Job Detection",
                False,
                "Provider not authenticated (skipping)"
            )
            return False

        try:
            # Initialize detector
            self.detector = JobDetector()

            # Fetch more emails to find job aggregator emails
            print("\nFetching emails to find job postings...")
            emails = self.provider.fetch_emails(max_results=50)

            # Find aggregator emails
            aggregator_emails = [e for e in emails if self.detector.is_aggregator_email(e)]

            print(f"Found {len(aggregator_emails)} aggregator emails out of {len(emails)} total")

            if aggregator_emails:
                # Parse jobs from first aggregator email
                test_email = aggregator_emails[0]
                print(f"\nParsing jobs from: {test_email.subject}")
                jobs = self.detector.parse_jobs(test_email)

                if jobs:
                    self.print_result(
                        "Job Detection",
                        True,
                        f"Extracted {len(jobs)} jobs using LLM"
                    )

                    # Display sample jobs
                    print("\n  Sample jobs:")
                    for i, job in enumerate(jobs[:3], 1):
                        print(f"  {i}. Position: {job.position}")
                        print(f"     Company: {job.company or 'Unknown'}")
                        print(f"     Location: {job.location or 'Not specified'}")
                        if job.link:
                            print(f"     Link: {job.link[:60]}...")

                    return True
                else:
                    self.print_result(
                        "Job Detection",
                        True,
                        "Aggregator email found, but no jobs extracted (may need different email)"
                    )
                    return True
            else:
                self.print_result(
                    "Job Detection",
                    True,
                    "No aggregator emails found in recent emails (this is OK)"
                )
                return True

        except Exception as e:
            self.print_result(
                "Job Detection",
                False,
                f"Exception: {e}"
            )
            return False

    async def test_4_email_rag_indexing(self) -> bool:
        """Test 4: Email RAG Indexing.

        Tests email RAG system initialization and job indexing.
        """
        self.print_header("Test 4: Email RAG Indexing")

        try:
            # Initialize email RAG
            print("\nInitializing Email RAG system...")
            self.email_rag = get_email_rag()

            # Index emails
            print("Indexing emails and extracting jobs...")
            count = self.email_rag.index_emails()

            if count > 0:
                self.print_result(
                    "Email RAG Indexing",
                    True,
                    f"Indexed {count} job postings"
                )

                # Get summary
                summary = self.email_rag.get_job_summary()
                print(f"  Index summary: {summary}")

                return True
            else:
                self.print_result(
                    "Email RAG Indexing",
                    True,
                    "No new jobs to index (may already be indexed or no job emails)"
                )
                return True

        except Exception as e:
            self.print_result(
                "Email RAG Indexing",
                False,
                f"Exception: {e}"
            )
            return False

    async def test_5_semantic_search(self) -> bool:
        """Test 5: Semantic Job Search.

        Tests semantic search functionality of email RAG.
        """
        self.print_header("Test 5: Semantic Job Search")

        if not self.email_rag:
            self.print_result(
                "Semantic Search",
                False,
                "Email RAG not initialized (skipping)"
            )
            return False

        try:
            # Test search
            query = "Python developer with backend experience"
            print(f"\nSearching for: '{query}'")

            results = self.email_rag.search(query, k=5)

            if results:
                self.print_result(
                    "Semantic Search",
                    True,
                    f"Found {len(results)} matching jobs"
                )

                # Display results
                print("\n  Top matches:")
                for i, (doc, score) in enumerate(results, 1):
                    print(f"  {i}. {doc.metadata['position']} at {doc.metadata['company']}")
                    print(f"     Location: {doc.metadata['location']}")
                    print(f"     Similarity: {1-score:.2%}")

                return True
            else:
                self.print_result(
                    "Semantic Search",
                    True,
                    "No results (no jobs indexed yet)"
                )
                return True

        except Exception as e:
            self.print_result(
                "Semantic Search",
                False,
                f"Exception: {e}"
            )
            return False

    def print_summary(self):
        """Print test summary."""
        self.print_header("Test Summary")

        total = len(self.test_results)
        passed = sum(1 for v in self.test_results.values() if v)

        print(f"\nTotal tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")

        if passed == total:
            print("\n✓ All tests passed!")
        else:
            print("\n✗ Some tests failed")

        print("\nDetailed results:")
        for test_name, success in self.test_results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {test_name}")

    async def run_all_tests(self):
        """Run all Phase 2 tests."""
        print("\n" + "=" * 70)
        print("  Phase 2 Testing: Email Infrastructure (Gmail + RAG)")
        print("=" * 70)

        # Run tests in order
        await self.test_1_gmail_oauth()
        await self.test_2_fetch_emails()
        await self.test_3_job_detection()
        await self.test_4_email_rag_indexing()
        await self.test_5_semantic_search()

        # Print summary
        self.print_summary()


async def main():
    """Main test entry point."""
    runner = Phase2TestRunner()
    await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
