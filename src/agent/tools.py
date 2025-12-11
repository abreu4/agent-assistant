"""Agent tools for file operations, web search, and code execution."""
from typing import List
from pathlib import Path

from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools.file_management import (
    ReadFileTool,
    ListDirectoryTool,
)

from ..utils.config import config
from ..utils.logging import get_logger

logger = get_logger("tools")


def get_agent_tools() -> List:
    """
    Get all available agent tools based on configuration.

    Returns:
        List of LangChain tools
    """
    tools = []

    # File operations (read-only)
    if config.get('tools.file_operations.enabled', True):
        tools.extend(_get_file_tools())

    # Document RAG (CV, cover letters)
    if config.get('tools.document_rag.enabled', True):
        tools.extend(_get_document_rag_tools())

    # Email and job tracking tools
    tools.extend(_get_email_job_tools())

    # Web search
    if config.get('tools.web_search.enabled', True):
        tools.append(_get_search_tool())

    # Code execution (disabled for job agent)
    if config.get('tools.code_execution.enabled', False):
        tools.append(_get_code_execution_tool())

    logger.info(f"Loaded {len(tools)} tools: {[t.name for t in tools]}")
    return tools


def _get_file_tools() -> List:
    """Get file operation tools (read-only for safety)."""
    workspace_dir = str(config.get_workspace_dir())  # Returns Path.cwd()

    tools = [
        ReadFileTool(root_dir=workspace_dir),
        # WriteFileTool removed for job agent safety
        ListDirectoryTool(root_dir=workspace_dir),
    ]

    # Add file search tool
    @tool
    def search_files(query: str) -> str:
        """
        Search for files in the workspace by name pattern.

        Args:
            query: Search pattern (e.g., '*.py', 'test*', 'data.json')

        Returns:
            List of matching file paths
        """
        try:
            workspace = Path(workspace_dir)
            matches = list(workspace.rglob(query))

            if not matches:
                return f"No files found matching '{query}'"

            results = "\n".join([
                str(p.relative_to(workspace)) for p in matches[:20]
            ])

            if len(matches) > 20:
                results += f"\n... and {len(matches) - 20} more files"

            return results

        except Exception as e:
            logger.error(f"File search error: {e}")
            return f"Error searching files: {e}"

    tools.append(search_files)
    return tools


def _get_search_tool():
    """Get web search tool."""
    import time
    provider = config.get('tools.web_search.provider', 'duckduckgo')

    if provider == 'duckduckgo':
        search = DuckDuckGoSearchRun()

        @tool
        def web_search(query: str) -> str:
            """
            Search the web for information.

            Args:
                query: Search query string

            Returns:
                Search results
            """
            max_retries = 3
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    logger.info(f"Web search: {query} (attempt {attempt + 1}/{max_retries})")
                    results = search.run(query)
                    return results
                except Exception as e:
                    error_msg = str(e).lower()

                    # Check if it's a rate limit error
                    if 'ratelimit' in error_msg or '202' in error_msg or '429' in error_msg:
                        if attempt < max_retries - 1:
                            logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} attempts")
                            return "Web search temporarily unavailable due to rate limiting. The agent can still answer your question without web search."
                    else:
                        logger.error(f"Web search error: {e}")
                        return f"Web search unavailable: {e}"

            return "Web search failed after multiple attempts."

        return web_search

    elif provider == 'tavily':
        # Optional: Tavily search (requires API key)
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults

            tavily_key = config.get_api_key('tavily')
            if not tavily_key:
                logger.warning("Tavily API key not found, falling back to DuckDuckGo")
                return _get_search_tool()  # Fallback to DuckDuckGo

            search = TavilySearchResults(api_key=tavily_key)

            @tool
            def web_search(query: str) -> str:
                """
                Search the web for information using Tavily.

                Args:
                    query: Search query string

                Returns:
                    Search results
                """
                try:
                    logger.info(f"Tavily search: {query}")
                    results = search.run(query)
                    return str(results)
                except Exception as e:
                    logger.error(f"Tavily search error: {e}")
                    return f"Search failed: {e}"

            return web_search

        except ImportError:
            logger.warning("Tavily not installed, falling back to DuckDuckGo")
            return _get_search_tool()  # Fallback

    else:
        logger.warning(f"Unknown search provider: {provider}, using DuckDuckGo")
        return _get_search_tool()


def _get_code_execution_tool():
    """Get code execution tool."""
    sandbox_type = config.get('tools.code_execution.sandbox', 'docker')

    if sandbox_type == 'disabled':
        @tool
        def execute_code(code: str, language: str = "python") -> str:
            """
            Code execution is disabled in configuration.

            Args:
                code: Code to execute
                language: Programming language

            Returns:
                Error message
            """
            return "Code execution is disabled. Enable it in config.yaml"

        return execute_code

    elif sandbox_type == 'docker':
        @tool
        def execute_python(code: str) -> str:
            """
            Execute Python code in a Docker sandbox.

            Args:
                code: Python code to execute

            Returns:
                Output of code execution or error message

            Warning:
                This executes arbitrary code in a Docker container.
                Ensure Docker is installed and running.
            """
            container = None
            try:
                import docker

                logger.info("Executing Python code in Docker sandbox")

                client = docker.from_env()

                # Get configuration
                timeout = config.get('tools.code_execution.timeout', 30)
                mem_limit = config.get('tools.code_execution.memory_limit', '256m')

                # Run code in Python container with restrictions
                container = client.containers.run(
                    "python:3.11-slim",
                    command=["python", "-c", code],
                    detach=True,
                    remove=False,  # Don't auto-remove, we need to get logs
                    network_disabled=True,
                    mem_limit=mem_limit,
                    cpu_quota=50000,
                    stdout=True,
                    stderr=True
                )

                logger.info(f"Container {container.short_id} started")

                # Wait for completion with timeout
                try:
                    result = container.wait(timeout=timeout)
                    exit_code = result.get('StatusCode', 0)

                    # Get logs (both stdout and stderr)
                    logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='ignore')

                    # Clean up
                    container.remove(force=True)
                    container = None

                    # Check exit code
                    if exit_code != 0:
                        logger.warning(f"Code execution exited with code {exit_code}")
                        return f"Code execution failed (exit code {exit_code}):\n{logs}"

                    logger.info("Code execution completed successfully")
                    return logs if logs.strip() else "Code executed successfully with no output"

                except docker.errors.APIError as e:
                    if "timeout" in str(e).lower():
                        logger.error(f"Container execution timeout after {timeout}s")
                        if container:
                            container.kill()
                            container.remove(force=True)
                            container = None
                        return f"Execution timeout after {timeout} seconds. Code took too long to execute."
                    raise

            except docker.errors.ImageNotFound:
                logger.error("Docker image not found")
                return "Docker image 'python:3.11-slim' not found. Pull it first: docker pull python:3.11-slim"

            except docker.errors.DockerException as e:
                logger.error(f"Docker error: {e}")
                error_msg = str(e)
                if "connection" in error_msg.lower() or "no such file" in error_msg.lower():
                    return "Docker is not running. Start Docker and try again."
                return f"Docker error: {e}"

            except Exception as e:
                logger.error(f"Code execution error: {e}")
                return f"Execution error: {e}"

            finally:
                # Ensure container cleanup
                if container:
                    try:
                        container.remove(force=True)
                        logger.info(f"Container {container.short_id} cleaned up")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup container: {cleanup_error}")

        return execute_python

    elif sandbox_type == 'restricted':
        # Simple restricted execution (NOT truly safe, use with caution)
        @tool
        def execute_python(code: str) -> str:
            """
            Execute Python code with RestrictedPython (limited safety).

            Args:
                code: Python code to execute

            Returns:
                Output or error message

            Warning:
                This is NOT fully sandboxed. For production, use Docker.
            """
            try:
                from RestrictedPython import compile_restricted, safe_globals
                import io
                import sys

                logger.warning("Using restricted Python execution (not fully safe)")

                # Compile with restrictions
                byte_code = compile_restricted(code, '<inline>', 'exec')

                if byte_code.errors:
                    return f"Compilation errors: {byte_code.errors}"

                # Setup restricted environment
                restricted_globals = safe_globals.copy()
                restricted_locals = {}

                # Capture stdout
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    exec(byte_code, restricted_globals, restricted_locals)
                    output = sys.stdout.getvalue()
                    return output if output else "Code executed successfully"

                finally:
                    sys.stdout = old_stdout

            except Exception as e:
                logger.error(f"Restricted execution error: {e}")
                return f"Execution error: {e}"

        return execute_python

    else:
        logger.warning(f"Unknown sandbox type: {sandbox_type}, disabling code execution")
        return _get_code_execution_tool()  # Returns disabled version


def _get_document_rag_tools() -> List:
    """Get document RAG tools for CV and cover letters."""
    from .document_rag import get_document_rag

    tools = []

    @tool
    def search_documents(query: str, file_type: str = None) -> str:
        """
        Search through CV, cover letters, and job application documents.
        Use this to find relevant experience, skills, or information from your documents.

        Args:
            query: What to search for (e.g., "Python experience", "leadership skills", "education")
            file_type: Optional file extension filter (e.g., ".pdf", ".txt")

        Returns:
            Relevant content from your documents
        """
        try:
            rag = get_document_rag()

            # Search for relevant chunks
            results = rag.search(query, k=3, filter_by_type=file_type)

            if not results:
                return f"No results found for '{query}' in your documents."

            # Format results
            output = f"Found {len(results)} relevant sections:\n\n"

            for i, (doc, score) in enumerate(results, 1):
                file_path = doc.metadata.get('file_name', 'unknown')
                content = doc.page_content.strip()

                output += f"[{i}] {file_path} (relevance: {1-score:.2f})\n"
                output += "```\n"
                output += content[:500]  # Limit to 500 chars
                if len(content) > 500:
                    output += "\n...(truncated)"
                output += "\n```\n\n"

            return output

        except Exception as e:
            logger.error(f"Document search error: {e}")
            return f"Search failed: {e}"

    @tool
    def list_documents() -> str:
        """
        Get overview of indexed job application documents.
        Shows summary of CVs, cover letters, and other documents.

        Returns:
            Document summary
        """
        try:
            rag = get_document_rag()
            summary = rag.get_document_summary()
            return summary

        except Exception as e:
            logger.error(f"List documents error: {e}")
            return f"Failed to list documents: {e}"

    tools.append(search_documents)
    tools.append(list_documents)

    return tools


def _get_email_job_tools() -> List:
    """Get email and job tracking tools."""
    from .tracking import get_job_manager, get_job_database

    tools = []

    @tool
    def search_emails(query: str, account_email: str = None, company: str = None, location: str = None) -> str:
        """
        Search through emails semantically for job-related content.

        Args:
            query: What to search for (e.g., "software engineer", "remote positions", "Python jobs")
            account_email: Optional email account to search (default: all accounts)
            company: Optional company name filter
            location: Optional location filter

        Returns:
            Relevant email excerpts with job information
        """
        try:
            from .email import get_email_rag

            rag = get_email_rag()

            # Search with filters
            results = rag.search(
                query=query,
                k=5,
                account_email=account_email,
                filter_company=company,
                filter_location=location
            )

            if not results:
                return f"No emails found matching '{query}'."

            # Format results
            output = f"Found {len(results)} relevant emails:\n\n"

            for i, (doc, score) in enumerate(results, 1):
                subject = doc.metadata.get('subject', 'No subject')
                sender = doc.metadata.get('sender', 'Unknown')
                date = doc.metadata.get('date', 'Unknown date')
                email_company = doc.metadata.get('company', 'N/A')
                position = doc.metadata.get('position', 'N/A')

                output += f"[{i}] From: {sender}\n"
                output += f"    Subject: {subject}\n"
                output += f"    Date: {date}\n"
                if email_company != 'N/A':
                    output += f"    Company: {email_company}\n"
                if position != 'N/A':
                    output += f"    Position: {position}\n"
                output += f"    Relevance: {1-score:.2f}\n\n"

            return output

        except Exception as e:
            logger.error(f"Email search error: {e}")
            return f"Email search failed: {e}"

    @tool
    def list_jobs(status: str = "new", company: str = None, limit: int = 20) -> str:
        """
        List tracked job postings from database.

        Args:
            status: Filter by status (new, interested, applied, interviewing, rejected, archived)
            company: Optional company name filter
            limit: Maximum number of jobs to return (default: 20)

        Returns:
            List of job postings with details
        """
        try:
            db = get_job_database()

            jobs = db.get_jobs(status=status if status != "all" else None,
                             company=company,
                             limit=limit)

            if not jobs:
                filters = f"status={status}" + (f", company={company}" if company else "")
                return f"No jobs found with filters: {filters}"

            # Format output
            output = f"Found {len(jobs)} job(s):\n\n"

            for job in jobs:
                output += f"[ID: {job['id']}] {job['position']}\n"
                output += f"  Company: {job['company'] or 'N/A'}\n"
                output += f"  Location: {job['location'] or 'N/A'}\n"
                output += f"  Status: {job['status']}\n"
                output += f"  Found: {job['found_date']}\n"
                if job['application_link']:
                    output += f"  Link: {job['application_link']}\n"
                if job['notes']:
                    output += f"  Notes: {job['notes'][:100]}...\n" if len(job['notes']) > 100 else f"  Notes: {job['notes']}\n"
                output += "\n"

            return output

        except Exception as e:
            logger.error(f"List jobs error: {e}")
            return f"Failed to list jobs: {e}"

    @tool
    def get_job_details(job_id: int) -> str:
        """
        Get full details of a specific job posting.

        Args:
            job_id: Job ID from database

        Returns:
            Complete job information
        """
        try:
            db = get_job_database()

            job = db.get_job_by_id(job_id)

            if not job:
                return f"Job with ID {job_id} not found."

            # Format output
            output = f"Job Details (ID: {job['id']}):\n\n"
            output += f"Position: {job['position']}\n"
            output += f"Company: {job['company'] or 'N/A'}\n"
            output += f"Location: {job['location'] or 'N/A'}\n"
            output += f"Job Type: {job['job_type'] or 'N/A'}\n"
            output += f"Salary: {job['salary'] or 'N/A'}\n"
            output += f"Status: {job['status']}\n"
            output += f"Found Date: {job['found_date']}\n"
            output += f"Email Date: {job['email_date']}\n"
            output += f"Account: {job['account_email']}\n"

            if job['application_link']:
                output += f"\nApplication Link:\n{job['application_link']}\n"

            if job['notes']:
                output += f"\nNotes:\n{job['notes']}\n"

            return output

        except Exception as e:
            logger.error(f"Get job details error: {e}")
            return f"Failed to get job details: {e}"

    @tool
    def update_job_status(job_id: int, status: str, notes: str = None) -> str:
        """
        Update job application status and add notes.

        Args:
            job_id: Job ID from database
            status: New status (new, interested, applied, interviewing, rejected, archived)
            notes: Optional notes to add or update

        Returns:
            Confirmation message
        """
        try:
            db = get_job_database()

            # Validate status
            valid_statuses = ['new', 'interested', 'applied', 'interviewing', 'rejected', 'archived']
            if status not in valid_statuses:
                return f"Invalid status. Valid options: {', '.join(valid_statuses)}"

            # Update job
            success = db.update_job_status(job_id, status, notes)

            if success:
                msg = f"✓ Job {job_id} updated to status: {status}"
                if notes:
                    msg += f"\n  Notes added: {notes[:50]}..." if len(notes) > 50 else f"\n  Notes added: {notes}"
                return msg
            else:
                return f"Failed to update job {job_id}. Job may not exist."

        except Exception as e:
            logger.error(f"Update job status error: {e}")
            return f"Failed to update job status: {e}"

    tools.extend([search_emails, list_jobs, get_job_details, update_job_status])

    return tools
