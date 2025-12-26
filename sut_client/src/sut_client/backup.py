"""
Backup Service for SUT Client
Handles backup and restore of game configurations
"""

import logging
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupService:
    """Service for managing configuration backups"""

    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, game_slug: str, file_path: Path) -> Optional[Path]:
        """
        Create a backup of a config file

        Args:
            game_slug: Game identifier
            file_path: Path to file to backup

        Returns:
            Path to backup file or None if failed
        """
        if not file_path.exists():
            logger.warning(f"File not found for backup: {file_path}")
            return None

        try:
            # Create game backup directory
            game_backup_dir = self.backup_dir / game_slug
            game_backup_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{game_slug}_{timestamp}_{file_path.name}"
            backup_path = game_backup_dir / backup_name

            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

            return backup_path

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    def restore_backup(self, game_slug: str, backup_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore from backup

        Args:
            game_slug: Game identifier
            backup_id: Specific backup to restore (optional, uses latest if not provided)

        Returns:
            Result dictionary
        """
        game_backup_dir = self.backup_dir / game_slug

        if not game_backup_dir.exists():
            return {"success": False, "error": f"No backups found for {game_slug}"}

        try:
            # Find backup to restore
            backups = sorted(game_backup_dir.glob(f"{game_slug}_*"), reverse=True)

            if not backups:
                return {"success": False, "error": "No backups available"}

            if backup_id:
                # Find specific backup
                backup_path = None
                for b in backups:
                    if backup_id in b.name:
                        backup_path = b
                        break
                if not backup_path:
                    return {"success": False, "error": f"Backup not found: {backup_id}"}
            else:
                backup_path = backups[0]  # Latest

            # TODO: Restore logic depends on original path tracking
            # For now, return the backup path
            return {
                "success": True,
                "backup_path": str(backup_path),
                "message": f"Backup found: {backup_path.name}"
            }

        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return {"success": False, "error": str(e)}

    def list_backups(self, game_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all backups

        Args:
            game_slug: Filter by game (optional)

        Returns:
            List of backup info dictionaries
        """
        backups = []

        try:
            if game_slug:
                game_dirs = [self.backup_dir / game_slug]
            else:
                game_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir()]

            for game_dir in game_dirs:
                if not game_dir.exists():
                    continue

                game_name = game_dir.name

                for backup_file in sorted(game_dir.glob("*"), reverse=True):
                    if backup_file.is_file():
                        stat = backup_file.stat()
                        backups.append({
                            "game": game_name,
                            "filename": backup_file.name,
                            "path": str(backup_file),
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

        except Exception as e:
            logger.error(f"Error listing backups: {e}")

        return backups

    def cleanup_old_backups(self, game_slug: str, keep_count: int = 5) -> int:
        """
        Remove old backups, keeping only the most recent N

        Args:
            game_slug: Game identifier
            keep_count: Number of backups to keep

        Returns:
            Number of backups deleted
        """
        game_backup_dir = self.backup_dir / game_slug

        if not game_backup_dir.exists():
            return 0

        backups = sorted(game_backup_dir.glob(f"{game_slug}_*"), reverse=True)

        deleted = 0
        for backup in backups[keep_count:]:
            try:
                backup.unlink()
                deleted += 1
                logger.info(f"Deleted old backup: {backup}")
            except Exception as e:
                logger.error(f"Error deleting backup {backup}: {e}")

        return deleted
