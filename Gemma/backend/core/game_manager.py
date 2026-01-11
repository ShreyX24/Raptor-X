# -*- coding: utf-8 -*-
# backend/core/game_manager.py
"""
Game configuration management for the new backend system
"""

import os
import glob
import yaml
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    """Game configuration data structure"""
    name: str
    path: str
    config_type: str  # 'steps' or 'state_machine'
    benchmark_duration: int
    resolution: str
    preset: str
    yaml_path: str
    startup_wait: int = 30  # Startup wait time in seconds (process detection timeout)
    init_wait: Optional[int] = None  # Post-launch initialization wait (if different from startup_wait)
    steam_app_id: Optional[str] = None  # Steam App ID for launching via Steam
    process_id: Optional[str] = None  # Process name to wait for after launch (launcher)
    game_process: Optional[str] = None  # Actual game process to track after launcher (e.g., "HITMAN3" for games with launchers)
    preset_id: Optional[str] = None  # Preset-manager game folder name (e.g., "cyberpunk-2077")
    launch_args: Optional[str] = None  # Command-line arguments for game (e.g., "-benchmark test.xml")
    launch_method: Optional[str] = None  # Launch method: 'steam' (default), 'exe' (direct executable), 'standalone'
    last_modified: Optional[datetime] = None
    hidden: bool = False  # Hidden configs (utility configs like steam_dialogs) don't appear in game lists
    # Standalone game fields (for benchmarks like FFXIV Dawntrail that aren't Steam games)
    standalone: bool = False  # If True, game is not a Steam game - find by folder name in steamapps/common/
    folder_names: Optional[List[str]] = None  # List of possible folder names to search for
    exe_name: Optional[str] = None  # Executable name (e.g., "ffxiv-dawntrail-bench.exe")
    preset_filename: Optional[str] = None  # Preset config filename to flash (e.g., "ffxivbenchmarklauncher.ini")
    # Window management
    minimize_others: bool = False  # If True, minimize other windows before automation


class GameConfigManager:
    """Manages game configurations for the backend"""
    
    def __init__(self, config_dir: str = "config/games"):
        self.config_dir = config_dir
        self.games: Dict[str, GameConfig] = {}
        self._ensure_config_dir()
        self.load_configurations()
        
        logger.info(f"GameConfigManager initialized with {len(self.games)} configurations")
    
    def _ensure_config_dir(self):
        """Ensure the configuration directory exists"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"Created game config directory: {self.config_dir}")
    
    def load_configurations(self) -> int:
        """
        Load all game configurations from YAML files
        
        Returns:
            Number of configurations loaded
        """
        self.games.clear()
        
        # Find all YAML files in the config directory
        yaml_patterns = [
            os.path.join(self.config_dir, "*.yaml"),
            os.path.join(self.config_dir, "*.yml")
        ]
        
        yaml_files = []
        for pattern in yaml_patterns:
            yaml_files.extend(glob.glob(pattern))
        
        if not yaml_files:
            logger.warning(f"No YAML configuration files found in {self.config_dir}")
            return 0
        
        loaded_count = 0
        for yaml_file in yaml_files:
            try:
                if self._load_single_config(yaml_file):
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load config {yaml_file}: {str(e)}")
        
        logger.info(f"Loaded {loaded_count} game configurations from {len(yaml_files)} files")
        return loaded_count
    
    def _load_single_config(self, yaml_file: str) -> bool:
        """
        Load a single game configuration file
        
        Args:
            yaml_file: Path to the YAML file
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                logger.warning(f"Empty configuration file: {yaml_file}")
                return False
            
            # Extract metadata
            metadata = config_data.get('metadata', {})
            
            # Determine game name
            game_name = metadata.get('game_name')
            if not game_name:
                # Fallback to filename without extension
                game_name = os.path.basename(yaml_file)
                for ext in ['.yaml', '.yml']:
                    if game_name.endswith(ext):
                        game_name = game_name[:-len(ext)]
                        break
            
            # Determine configuration type
            config_type = 'steps' if 'steps' in config_data else 'state_machine'
            
            # Get file modification time
            stat = os.stat(yaml_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Create game configuration
            game_config = GameConfig(
                name=game_name,
                path=metadata.get('path', ''),
                config_type=config_type,
                benchmark_duration=metadata.get('benchmark_duration', 120),
                resolution=metadata.get('resolution', '1920x1080'),
                preset=metadata.get('preset', 'High'),
                yaml_path=yaml_file,
                startup_wait=metadata.get('startup_wait', 30),
                init_wait=metadata.get('init_wait'),  # Post-launch initialization wait
                steam_app_id=metadata.get('steam_app_id'),  # Steam App ID for launching
                process_id=metadata.get('process_id'),  # Process name to wait for after launch (launcher)
                game_process=metadata.get('game_process'),  # Actual game process after launcher
                preset_id=metadata.get('preset_id'),  # Preset-manager game folder name
                launch_args=metadata.get('launch_args'),  # Command-line arguments for game
                launch_method=metadata.get('launch_method'),  # Launch method: 'steam', 'exe', or 'standalone'
                last_modified=last_modified,
                hidden=metadata.get('hidden', False),  # Hidden configs don't appear in game lists
                # Standalone game fields
                standalone=metadata.get('standalone', False),
                folder_names=metadata.get('folder_names'),  # List of folder names to search
                exe_name=metadata.get('exe_name'),  # Executable filename
                preset_filename=metadata.get('preset_filename'),  # Preset config filename
                # Window management
                minimize_others=metadata.get('minimize_others', False),
            )
            
            # Store the configuration
            self.games[game_name] = game_config
            logger.debug(f"Loaded game config: {game_name} ({config_type}) from {yaml_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration {yaml_file}: {str(e)}")
            return False
    
    def get_all_games(self, include_hidden: bool = False) -> Dict[str, GameConfig]:
        """Get all loaded game configurations (excluding hidden by default)"""
        if include_hidden:
            return self.games.copy()
        return {name: config for name, config in self.games.items() if not config.hidden}
    
    def get_game(self, name: str) -> Optional[GameConfig]:
        """Get a specific game configuration by name"""
        return self.games.get(name)
    
    def reload_configurations(self) -> Dict[str, Any]:
        """
        Reload all configurations and return statistics
        
        Returns:
            Dictionary with reload statistics
        """
        old_count = len(self.games)
        new_count = self.load_configurations()
        
        stats = {
            'status': 'success',
            'old_count': old_count,
            'new_count': new_count,
            'games': list(self.games.keys()),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Configuration reload: {old_count} -> {new_count} games")
        return stats
    
    def get_game_stats(self, include_hidden: bool = False) -> Dict[str, Any]:
        """Get statistics about loaded games (excluding hidden by default)"""
        visible_games = self.get_all_games(include_hidden=include_hidden)

        if not visible_games:
            return {
                'total_games': 0,
                'config_types': {},
                'games': []
            }

        config_types = {}
        for game in visible_games.values():
            config_types[game.config_type] = config_types.get(game.config_type, 0) + 1

        # Convert games to dict format with proper datetime handling
        games_list = []
        for game in visible_games.values():
            game_dict = asdict(game)
            if game_dict.get('last_modified'):
                game_dict['last_modified'] = game.last_modified.isoformat()
            games_list.append(game_dict)

        return {
            'total_games': len(visible_games),
            'config_types': config_types,
            'games': games_list
        }
    
    def to_dict(self, include_hidden: bool = False) -> Dict[str, Dict[str, Any]]:
        """Convert all games to dictionary format for API/WebSocket (excluding hidden by default)"""
        result = {}
        visible_games = self.get_all_games(include_hidden=include_hidden)
        for name, config in visible_games.items():
            config_dict = asdict(config)
            # Convert datetime to ISO string for JSON serialization
            if config_dict.get('last_modified'):
                config_dict['last_modified'] = config.last_modified.isoformat()
            result[name] = config_dict
        return result

    # ============== YAML CRUD Operations ==============

    def get_game_yaml(self, name: str) -> Optional[str]:
        """
        Get raw YAML content for a game configuration

        Args:
            name: Game name

        Returns:
            Raw YAML string or None if not found
        """
        game = self.games.get(name)
        if not game:
            logger.warning(f"Game not found: {name}")
            return None

        try:
            with open(game.yaml_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read YAML for {name}: {e}")
            return None

    def save_game_yaml(self, name: str, content: str) -> Dict[str, Any]:
        """
        Save raw YAML content for an existing game configuration

        Args:
            name: Game name
            content: Raw YAML string

        Returns:
            Dict with status and any errors
        """
        game = self.games.get(name)
        if not game:
            return {'status': 'error', 'error': f'Game not found: {name}'}

        # Validate YAML syntax first
        validation = self.validate_yaml(content)
        if not validation['valid']:
            return {'status': 'error', 'error': 'Invalid YAML', 'details': validation['errors']}

        try:
            # Write to file
            with open(game.yaml_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Reload this config to update in-memory state
            self._load_single_config(game.yaml_path)

            logger.info(f"Saved YAML for game: {name}")
            return {'status': 'success', 'message': f'Saved {name}'}

        except Exception as e:
            logger.error(f"Failed to save YAML for {name}: {e}")
            return {'status': 'error', 'error': str(e)}

    def create_game(self, name: str, content: str) -> Dict[str, Any]:
        """
        Create a new game configuration file

        Args:
            name: Game name (will be used for filename)
            content: Raw YAML string

        Returns:
            Dict with status and any errors
        """
        # Sanitize name for filename
        safe_name = name.lower().replace(' ', '-').replace('_', '-')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '-')

        yaml_path = os.path.join(self.config_dir, f"{safe_name}.yaml")

        # Check if file already exists
        if os.path.exists(yaml_path):
            return {'status': 'error', 'error': f'Game config already exists: {safe_name}.yaml'}

        # Validate YAML syntax
        validation = self.validate_yaml(content)
        if not validation['valid']:
            return {'status': 'error', 'error': 'Invalid YAML', 'details': validation['errors']}

        try:
            # Write new file
            with open(yaml_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Load the new config
            self._load_single_config(yaml_path)

            logger.info(f"Created new game config: {safe_name}.yaml")
            return {
                'status': 'success',
                'message': f'Created {safe_name}.yaml',
                'filename': f'{safe_name}.yaml',
                'path': yaml_path
            }

        except Exception as e:
            logger.error(f"Failed to create game config: {e}")
            return {'status': 'error', 'error': str(e)}

    def delete_game(self, name: str) -> Dict[str, Any]:
        """
        Delete a game configuration file

        Args:
            name: Game name

        Returns:
            Dict with status and any errors
        """
        game = self.games.get(name)
        if not game:
            return {'status': 'error', 'error': f'Game not found: {name}'}

        yaml_path = game.yaml_path

        try:
            # Remove file
            os.remove(yaml_path)

            # Remove from in-memory dict
            del self.games[name]

            logger.info(f"Deleted game config: {name}")
            return {'status': 'success', 'message': f'Deleted {name}'}

        except Exception as e:
            logger.error(f"Failed to delete game config {name}: {e}")
            return {'status': 'error', 'error': str(e)}

    def validate_yaml(self, content: str) -> Dict[str, Any]:
        """
        Validate YAML content syntax and structure

        Args:
            content: Raw YAML string

        Returns:
            Dict with 'valid' bool and 'errors' list
        """
        errors = []

        # Check for empty content
        if not content or not content.strip():
            return {'valid': False, 'errors': ['YAML content is empty']}

        # Parse YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_msg = str(e)
            # Try to extract line number from YAML error
            return {'valid': False, 'errors': [f'YAML syntax error: {error_msg}']}

        # Check if it's a valid dict
        if not isinstance(data, dict):
            return {'valid': False, 'errors': ['YAML must be a dictionary/object']}

        # Validate structure
        if 'metadata' not in data:
            errors.append('Missing "metadata" section')
        else:
            metadata = data['metadata']
            if not isinstance(metadata, dict):
                errors.append('"metadata" must be a dictionary')
            elif 'game_name' not in metadata:
                errors.append('Missing "game_name" in metadata')

        if 'steps' not in data and 'states' not in data:
            errors.append('Missing "steps" or "states" section')

        if 'steps' in data:
            steps = data['steps']
            if not isinstance(steps, dict):
                errors.append('"steps" must be a dictionary with step numbers as keys')
            else:
                for step_num, step_data in steps.items():
                    if not isinstance(step_data, dict):
                        errors.append(f'Step {step_num} must be a dictionary')
                        continue
                    if 'description' not in step_data:
                        errors.append(f'Step {step_num} missing "description"')

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': []  # Could add warnings for best practices
        }

    def get_workflow_summary(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a workflow for display in UI

        Args:
            name: Game name

        Returns:
            Dict with summary info or None if not found
        """
        game = self.games.get(name)
        if not game:
            return None

        # Read and parse YAML to count steps
        step_count = 0
        try:
            with open(game.yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if 'steps' in data and isinstance(data['steps'], dict):
                step_count = len(data['steps'])
        except Exception as e:
            logger.warning(f"Failed to get step count for {name}: {e}")

        return {
            'name': game.name,
            'filename': os.path.basename(game.yaml_path),
            'config_type': game.config_type,
            'step_count': step_count,
            'last_modified': game.last_modified.isoformat() if game.last_modified else None,
            'steam_app_id': game.steam_app_id,
            'preset_id': game.preset_id
        }

    def list_workflows(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of all workflows with summaries (excluding hidden by default)

        Returns:
            List of workflow summaries
        """
        summaries = []
        visible_games = self.get_all_games(include_hidden=include_hidden)
        for name in visible_games:
            summary = self.get_workflow_summary(name)
            if summary:
                summaries.append(summary)

        # Sort by name
        summaries.sort(key=lambda x: x['name'].lower())
        return summaries