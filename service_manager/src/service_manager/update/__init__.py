"""
Update module for RPX Service Manager.
Handles checking for updates and pulling from git repositories.
"""

from .update_manager import UpdateManager, RepoConfig, UpdateResult

__all__ = ["UpdateManager", "RepoConfig", "UpdateResult"]
