"""Agent tools for file operations, web search, and code execution."""
from typing import List
from pathlib import Path

from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools.file_management import (
    ReadFileTool,
    WriteFileTool,
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

    # File operations
    if config.get('tools.file_operations.enabled', True):
        tools.extend(_get_file_tools())

    # Web search
    if config.get('tools.web_search.enabled', True):
        tools.append(_get_search_tool())

    # Code execution
    if config.get('tools.code_execution.enabled', True):
        tools.append(_get_code_execution_tool())

    logger.info(f"Loaded {len(tools)} tools: {[t.name for t in tools]}")
    return tools


def _get_file_tools() -> List:
    """Get file operation tools."""
    workspace_dir = str(config.get_workspace_dir())

    tools = [
        ReadFileTool(root_dir=workspace_dir),
        WriteFileTool(root_dir=workspace_dir),
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
