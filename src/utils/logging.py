"""Logging configuration for Agent Assistant."""
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from systemd.journal import JournalHandler
    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False


def setup_logging(
    log_level: str = "INFO",
    use_systemd: bool = True,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        use_systemd: Whether to use systemd journal handler
        log_file: Optional path to log file

    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger("agent_assistant")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add systemd journal handler if available and requested
    if use_systemd and HAS_SYSTEMD:
        journal_handler = JournalHandler()
        journal_handler.setFormatter(formatter)
        logger.addHandler(journal_handler)
    else:
        # Fall back to stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger.

    Args:
        name: Logger name (will be prefixed with 'agent_assistant.')

    Returns:
        Logger instance
    """
    return logging.getLogger(f"agent_assistant.{name}")
