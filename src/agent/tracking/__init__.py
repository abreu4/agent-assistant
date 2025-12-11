"""Job tracking system - database and orchestration for job applications."""

from .database import JobDatabase, get_job_database
from .manager import JobManager, get_job_manager

__all__ = [
    'JobDatabase',
    'get_job_database',
    'JobManager',
    'get_job_manager',
]
