#!/usr/bin/env python3
"""
Migration script to reorganize existing campaign folders from flat structure
to game-grouped structure.

Before:
    campaign-folder/
    +-- 2026-01-08_..._single-Far Cry 6/       (game1, run 1)
    +-- 2026-01-08_..._single-Shadow of TR/    (game2, run 1)
    +-- 2026-01-08_..._single-Far Cry 6/       (game1, run 2)
    +-- campaign_manifest.json

After:
    campaign-folder/
    +-- Far-Cry-6/
    |   +-- perf-run-1/
    |   +-- perf-run-2/
    +-- Shadow-of-the-Tomb-Raider/
    |   +-- perf-run-1/
    |   +-- perf-run-2/
    +-- campaign_manifest.json

Usage:
    python migrate_campaign_logs.py [--dry-run] [--logs-dir PATH]
"""

import argparse
import json
import logging
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sanitize_folder_name(name: str) -> str:
    """Sanitize a string for use as folder name."""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with dashes
    sanitized = sanitized.replace(' ', '-')
    return sanitized


def extract_game_name_from_folder(folder_name: str) -> str:
    """
    Extract game name from legacy folder name format.

    Format: YYYY-MM-DD_HHMMSS_CPU_IP_single-GAME_NAME
    Example: 2026-01-08_032805_10875H_192-168-0-103_single-Far Cry 6

    Returns: Game name (e.g., "Far Cry 6")
    """
    # Look for "single-" pattern
    match = re.search(r'single-(.+)$', folder_name)
    if match:
        return match.group(1)

    # Look for "bulk-" pattern (multiple games)
    match = re.search(r'bulk-(.+)$', folder_name)
    if match:
        # Return first game from bulk run
        games_part = match.group(1)
        # Split on "-and" or just take first segment
        first_game = games_part.split('-and')[0]
        return first_game

    return "Unknown"


def get_folder_timestamp(folder_name: str) -> datetime:
    """Extract timestamp from folder name for sorting."""
    # Format: YYYY-MM-DD_HHMMSS_...
    match = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{6})_', folder_name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        try:
            return datetime.strptime(f"{date_str}_{time_str}", "%Y-%m-%d_%H%M%S")
        except ValueError:
            pass
    return datetime.min


def is_legacy_run_folder(folder: Path) -> bool:
    """Check if a folder is a legacy run folder (not already migrated)."""
    # Legacy folders have the pattern: YYYY-MM-DD_HHMMSS_..._single-GAME
    # New folders are just "perf-run-N"
    name = folder.name
    if name.startswith('perf-run-'):
        return False
    if re.match(r'\d{4}-\d{2}-\d{2}_\d{6}_', name):
        return True
    return False


def is_campaign_folder(folder: Path) -> bool:
    """Check if a folder is a campaign folder."""
    return (folder / 'campaign_manifest.json').exists()


def migrate_campaign(campaign_folder: Path, dry_run: bool = False) -> Tuple[int, int]:
    """
    Migrate a single campaign folder to the new structure.

    Args:
        campaign_folder: Path to campaign folder
        dry_run: If True, only show what would be done

    Returns:
        Tuple of (runs_migrated, runs_failed)
    """
    logger.info(f"Processing campaign: {campaign_folder.name}")

    # Find all legacy run folders
    legacy_runs: Dict[str, List[Tuple[Path, datetime]]] = defaultdict(list)

    for item in campaign_folder.iterdir():
        if item.is_dir() and is_legacy_run_folder(item):
            game_name = extract_game_name_from_folder(item.name)
            timestamp = get_folder_timestamp(item.name)
            legacy_runs[game_name].append((item, timestamp))
            logger.debug(f"  Found legacy run: {item.name} -> game={game_name}")

    if not legacy_runs:
        logger.info(f"  No legacy runs to migrate (already migrated or empty)")
        return (0, 0)

    runs_migrated = 0
    runs_failed = 0

    # Process each game
    for game_name, runs in legacy_runs.items():
        # Sort runs by timestamp
        runs.sort(key=lambda x: x[1])

        # Create sanitized game folder name
        game_folder_name = sanitize_folder_name(game_name)
        game_folder = campaign_folder / game_folder_name

        logger.info(f"  Game: {game_name} ({len(runs)} runs) -> {game_folder_name}/")

        if not dry_run:
            game_folder.mkdir(exist_ok=True)

        # Move each run with new naming
        for idx, (run_folder, _) in enumerate(runs, start=1):
            new_name = f"perf-run-{idx}"
            new_path = game_folder / new_name

            logger.info(f"    {run_folder.name} -> {game_folder_name}/{new_name}")

            if not dry_run:
                try:
                    # Move the folder
                    shutil.move(str(run_folder), str(new_path))

                    # Update manifest.json inside the run folder if it exists
                    manifest_path = new_path / 'manifest.json'
                    if manifest_path.exists():
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)

                        # Update folder_name to new structure
                        old_folder_name = manifest.get('folder_name', '')
                        new_folder_name = f"{campaign_folder.name}/{game_folder_name}/{new_name}"
                        manifest['folder_name'] = new_folder_name

                        # Add migration metadata
                        manifest['_migrated'] = {
                            'from': old_folder_name,
                            'to': new_folder_name,
                            'migrated_at': datetime.now().isoformat()
                        }

                        with open(manifest_path, 'w', encoding='utf-8') as f:
                            json.dump(manifest, f, indent=2)

                    runs_migrated += 1
                except Exception as e:
                    logger.error(f"    Failed to migrate: {e}")
                    runs_failed += 1
            else:
                runs_migrated += 1

    return (runs_migrated, runs_failed)


def migrate_all_campaigns(logs_dir: Path, dry_run: bool = False) -> Dict[str, any]:
    """
    Migrate all campaign folders in the logs directory.

    Args:
        logs_dir: Path to logs/runs directory
        dry_run: If True, only show what would be done

    Returns:
        Migration statistics
    """
    stats = {
        'campaigns_found': 0,
        'campaigns_migrated': 0,
        'campaigns_skipped': 0,
        'runs_migrated': 0,
        'runs_failed': 0,
        'errors': []
    }

    if not logs_dir.exists():
        logger.error(f"Logs directory not found: {logs_dir}")
        return stats

    logger.info(f"Scanning for campaigns in: {logs_dir}")
    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made")
    logger.info("")

    # Find all campaign folders
    for folder in sorted(logs_dir.iterdir()):
        if folder.is_dir() and is_campaign_folder(folder):
            stats['campaigns_found'] += 1

            try:
                migrated, failed = migrate_campaign(folder, dry_run)

                if migrated > 0:
                    stats['campaigns_migrated'] += 1
                else:
                    stats['campaigns_skipped'] += 1

                stats['runs_migrated'] += migrated
                stats['runs_failed'] += failed

            except Exception as e:
                logger.error(f"Error processing campaign {folder.name}: {e}")
                stats['errors'].append(str(e))

            logger.info("")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Migrate campaign logs to game-grouped structure'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--logs-dir', '-d',
        type=Path,
        default=None,
        help='Path to logs/runs directory (default: Gemma/logs/runs)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine logs directory
    if args.logs_dir:
        logs_dir = args.logs_dir
    else:
        # Default: look relative to script location
        script_dir = Path(__file__).parent
        gemma_dir = script_dir.parent
        logs_dir = gemma_dir / "logs" / "runs"

    logger.info("=" * 60)
    logger.info("Campaign Log Migration Tool")
    logger.info("=" * 60)
    logger.info("")

    # Run migration
    stats = migrate_all_campaigns(logs_dir, dry_run=args.dry_run)

    # Print summary
    logger.info("=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"  Campaigns found:    {stats['campaigns_found']}")
    logger.info(f"  Campaigns migrated: {stats['campaigns_migrated']}")
    logger.info(f"  Campaigns skipped:  {stats['campaigns_skipped']} (already migrated)")
    logger.info(f"  Runs migrated:      {stats['runs_migrated']}")
    logger.info(f"  Runs failed:        {stats['runs_failed']}")

    if stats['errors']:
        logger.warning(f"  Errors: {len(stats['errors'])}")
        for err in stats['errors']:
            logger.warning(f"    - {err}")

    if args.dry_run:
        logger.info("")
        logger.info("This was a DRY RUN. Run without --dry-run to apply changes.")

    return 0 if stats['runs_failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
