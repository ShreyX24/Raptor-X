"""
Preset Applier for SUT Client
Handles applying received presets to the local system
"""

import os
import re
import logging
import base64
import shutil
import glob
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .backup import BackupService
from .system import kill_process

logger = logging.getLogger(__name__)


def find_steam_install() -> str:
    """Find Steam installation directory"""
    # Common Steam install locations
    possible_paths = [
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Steam'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Steam'),
        'C:\\Steam',
        'D:\\Steam',
        'E:\\Steam',
        'D:\\SteamLibrary',
        'E:\\SteamLibrary',
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Steam')


class PresetApplier:
    """Applies presets received from Master to local system"""

    # Environment variable mappings
    ENV_MAPPINGS = {
        '%USERPROFILE%': os.environ.get('USERPROFILE', os.path.expanduser('~')),
        '%LOCALAPPDATA%': os.environ.get('LOCALAPPDATA', ''),
        '%APPDATA%': os.environ.get('APPDATA', ''),
        '%PROGRAMFILES%': os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
        '%PROGRAMFILES(X86)%': os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'),
        '%PROGRAMDATA%': os.environ.get('PROGRAMDATA', 'C:\\ProgramData'),
        '%STEAM_INSTALL%': find_steam_install(),
    }

    def __init__(self, backup_service: BackupService):
        self.backup_service = backup_service
        self._game_path_cache: Dict[str, Optional[Path]] = {}

    def parse_vdf_simple(self, content: str) -> Dict:
        """
        Parse Valve VDF format (libraryfolders.vdf, appmanifest)

        Args:
            content: VDF file content as string

        Returns:
            Dictionary of parsed data
        """
        result = {}
        stack = [result]
        current = result

        lines = [line.strip() for line in content.split('\n')]
        for line in lines:
            if not line or line.startswith('//') or line == '{':
                continue
            if line == '}':
                if len(stack) > 1:
                    stack.pop()
                    current = stack[-1]
                continue
            # Key-value: "key"  "value"
            match = re.match(r'"([^"]+)"\s+"([^"]*)"', line)
            if match:
                current[match.group(1)] = match.group(2)
                continue
            # Key with nested object: "key"
            match = re.match(r'"([^"]+)"', line)
            if match:
                new_dict = {}
                current[match.group(1)] = new_dict
                stack.append(new_dict)
                current = new_dict
        return result

    def get_steam_libraries(self) -> List[Path]:
        """
        Get all Steam library paths by parsing libraryfolders.vdf

        Returns:
            List of Path objects for each Steam library
        """
        steam_path = Path(self.ENV_MAPPINGS.get('%STEAM_INSTALL%', ''))
        vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"

        if not vdf_path.exists():
            logger.warning(f"libraryfolders.vdf not found at {vdf_path}")
            return [steam_path]  # Fallback to default

        try:
            with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = self.parse_vdf_simple(f.read())

            libraries = []
            if 'libraryfolders' in data:
                for key, value in data['libraryfolders'].items():
                    if isinstance(value, dict) and 'path' in value:
                        lib_path = Path(value['path'])
                        if lib_path.exists():
                            libraries.append(lib_path)
                            logger.debug(f"Found Steam library: {lib_path}")

            return libraries if libraries else [steam_path]

        except Exception as e:
            logger.error(f"Error parsing libraryfolders.vdf: {e}")
            return [steam_path]

    def find_game_path_by_app_id(self, app_id: str) -> Optional[Path]:
        """
        Find game installation path by Steam app ID

        Args:
            app_id: Steam app ID (e.g., "2488620" for F1 24)

        Returns:
            Path to game installation directory, or None if not found
        """
        # Check cache first
        if app_id in self._game_path_cache:
            return self._game_path_cache[app_id]

        for library in self.get_steam_libraries():
            manifest = library / "steamapps" / f"appmanifest_{app_id}.acf"
            if manifest.exists():
                try:
                    with open(manifest, 'r', encoding='utf-8', errors='ignore') as f:
                        data = self.parse_vdf_simple(f.read())

                    if 'AppState' in data and 'installdir' in data['AppState']:
                        installdir = data['AppState']['installdir']
                        game_path = library / "steamapps" / "common" / installdir
                        if game_path.exists():
                            logger.info(f"Found game {app_id} at: {game_path}")
                            self._game_path_cache[app_id] = game_path
                            return game_path
                except Exception as e:
                    logger.error(f"Error parsing appmanifest for {app_id}: {e}")

        logger.warning(f"Game with app ID {app_id} not found in any Steam library")
        self._game_path_cache[app_id] = None
        return None

    def _backup_registry_key(self, registry_path: str, game_short_name: str) -> Optional[str]:
        """
        Backup a registry key using reg export command

        Args:
            registry_path: Registry key path (e.g., HKEY_CURRENT_USER\\SOFTWARE\\...)
            game_short_name: Game identifier for backup naming

        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            # Create backup directory
            backup_dir = self.backup_service.backup_dir / game_short_name / "registry"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            key_name = registry_path.split("\\")[-1]
            backup_file = backup_dir / f"{key_name}_{timestamp}.reg"

            # Run reg export command
            cmd = f'reg export "{registry_path}" "{backup_file}" /y'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.info(f"Registry backup created: {backup_file}")
                return str(backup_file)
            else:
                logger.warning(f"Registry backup failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error backing up registry key: {e}")
            return None

    def _apply_registry_preset(
        self,
        config_path: str,
        file_content_map: Dict[str, bytes],
        game_short_name: str,
        create_backup: bool,
        result: Dict[str, Any]
    ):
        """
        Apply a registry preset using reg import command

        Args:
            config_path: Registry key path from config
            file_content_map: Map of filenames to content bytes
            game_short_name: Game identifier
            create_backup: Whether to backup existing registry
            result: Result dictionary to update
        """
        try:
            # Find the .reg file in the preset
            reg_content = None
            reg_filename = None

            for filename, content in file_content_map.items():
                if filename.lower().endswith('.reg'):
                    reg_content = content
                    reg_filename = filename
                    break

            if not reg_content:
                result["errors"].append(f"No .reg file found for registry config: {config_path}")
                return

            # Backup existing registry key if requested
            if create_backup:
                backup_path = self._backup_registry_key(config_path, game_short_name)
                if backup_path:
                    result["backups_created"].append(backup_path)

            # Write .reg content to temp file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.reg', delete=False) as temp_file:
                temp_file.write(reg_content)
                temp_path = temp_file.name

            try:
                # Import registry file using reg import
                cmd = f'reg import "{temp_path}"'
                import_result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True
                )

                if import_result.returncode == 0:
                    result["files_applied"].append(f"Registry: {config_path} ({reg_filename})")
                    logger.info(f"Applied registry preset: {config_path}")
                else:
                    error_msg = f"Registry import failed for {config_path}: {import_result.stderr}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except Exception as e:
            error_msg = f"Error applying registry preset: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)

    def _merge_hardware_config(
        self,
        preset_content: bytes,
        existing_path: Path,
        config_def: Dict[str, Any]
    ) -> bytes:
        """
        Merge hardware-specific values from existing config into preset.
        Used for games like F1 24 that embed CPU/GPU info in config files.

        Args:
            preset_content: The preset file content (bytes)
            existing_path: Path to existing config on target system
            config_def: Config definition with merge rules

        Returns:
            Modified preset content with hardware values preserved
        """
        preserve_hardware = config_def.get('preserve_hardware', False)
        if not preserve_hardware or not existing_path.exists():
            return preset_content

        try:
            import xml.etree.ElementTree as ET

            # Parse existing config
            existing_tree = ET.parse(existing_path)
            existing_root = existing_tree.getroot()

            # Parse preset content
            preset_root = ET.fromstring(preset_content.decode('utf-8'))

            # Preserve <cpu> element attributes from existing
            existing_cpu = existing_root.find('cpu')
            preset_cpu = preset_root.find('cpu')
            if existing_cpu is not None and preset_cpu is not None:
                for attr in ['name', 'processors', 'processorStride', 'processorBinding']:
                    if attr in existing_cpu.attrib:
                        preset_cpu.set(attr, existing_cpu.get(attr))
                logger.info(f"Preserved CPU config: {existing_cpu.get('name')}")

            # Preserve graphics_card deviceId from existing
            existing_gpu = existing_root.find('graphics_card')
            preset_gpu = preset_root.find('graphics_card')
            if existing_gpu is not None and preset_gpu is not None:
                if 'deviceId' in existing_gpu.attrib:
                    preset_gpu.set('deviceId', existing_gpu.get('deviceId'))
                    logger.info(f"Preserved GPU deviceId: {existing_gpu.get('deviceId')}")

            # Convert back to bytes with XML declaration
            xml_declaration = '<?xml version="1.0" encoding="UTF-8" ?>\n'
            xml_content = ET.tostring(preset_root, encoding='unicode')
            return (xml_declaration + xml_content).encode('utf-8')

        except Exception as e:
            logger.warning(f"Failed to merge hardware config: {e}, using preset as-is")
            return preset_content

    def expand_path(self, path_string: str) -> str:
        """Expand environment variables in path"""
        if not path_string:
            return ""

        expanded = path_string

        # Handle %STEAM_GAME_<appid>% pattern for dynamic game path resolution
        steam_game_match = re.search(r'%STEAM_GAME_(\d+)%', expanded, re.IGNORECASE)
        if steam_game_match:
            app_id = steam_game_match.group(1)
            game_path = self.find_game_path_by_app_id(app_id)
            if game_path:
                # Use string replace instead of re.sub to avoid escape issues with backslashes
                pattern = steam_game_match.group(0)  # The full match like %STEAM_GAME_2488620%
                expanded = expanded.replace(pattern, str(game_path))
            else:
                logger.warning(f"Could not resolve %STEAM_GAME_{app_id}% - game not found")

        # Handle standard environment variable mappings
        for env_var, env_value in self.ENV_MAPPINGS.items():
            if env_var in expanded.upper():
                expanded = expanded.replace(env_var, env_value)
                expanded = expanded.replace(env_var.lower(), env_value)

        return expanded.replace('\\', os.sep)

    def resolve_config_path(self, config_path: str) -> Optional[Path]:
        """
        Resolve config path, trying multiple variants for Documents folder
        """
        expanded = self.expand_path(config_path)

        # Try multiple variants for Documents folder
        path_upper = expanded.upper()
        userprofile = self.ENV_MAPPINGS.get('%USERPROFILE%', '')

        if 'DOCUMENTS' in path_upper:
            variants = [
                expanded,  # Original
                expanded.replace('Documents', 'OneDrive\\Documents'),
                expanded.replace('documents', 'OneDrive\\Documents'),
            ]

            for variant in variants:
                path = Path(variant)
                if path.parent.exists():
                    return path

        return Path(expanded)

    def get_available_drives(self) -> List[str]:
        """
        Get all available drive letters on Windows.

        Returns:
            List of drive letters (e.g., ['C:', 'D:', 'E:'])
        """
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(f"{letter}:")
        return drives

    def resolve_search_paths(self, search_paths: List[str], filename: str) -> Optional[Path]:
        """
        Search multiple paths for a file. Used for standalone apps like FFXIV benchmark
        that can be installed in various locations.

        Args:
            search_paths: List of paths to search (with env variables)
                         Use %ALL_DRIVES% as placeholder to search all available drives
            filename: The config filename to look for

        Returns:
            First path where the file exists, or first path where parent exists, or None
        """
        found_paths = []
        expanded_search_paths = []

        # Expand %ALL_DRIVES% placeholder to all available drives
        for search_path in search_paths:
            if '%ALL_DRIVES%' in search_path.upper():
                for drive in self.get_available_drives():
                    expanded = search_path.replace('%ALL_DRIVES%', drive)
                    expanded = expanded.replace('%all_drives%', drive)
                    expanded_search_paths.append(expanded)
            else:
                expanded_search_paths.append(search_path)

        for search_path in expanded_search_paths:
            expanded = self.expand_path(search_path)
            full_path = Path(expanded) / filename

            if full_path.exists():
                logger.info(f"Found config at: {full_path}")
                return full_path
            elif full_path.parent.exists():
                # Parent exists, file might be created
                found_paths.append(full_path)
                logger.debug(f"Parent exists for: {full_path}")

        # Return first path where parent exists (for new installs)
        if found_paths:
            logger.info(f"Using path (parent exists): {found_paths[0]}")
            return found_paths[0]

        logger.warning(f"No valid path found for {filename} in search paths")
        return None

    def _apply_to_wildcard_path(
        self,
        config_path: str,
        config_def: Dict[str, Any],
        file_content_map: Dict[str, bytes],
        game_short_name: str,
        create_backup: bool,
        result: Dict[str, Any]
    ):
        """
        Handle paths with wildcards or apply_to_all_subfolders flag.
        E.g., ...SaveGames/**/UserSettingSaveGame.sav
        """
        expanded_path = self.expand_path(config_path)

        # Extract the filename from the path
        if '*' in expanded_path:
            # Split at the wildcard
            base_part, wildcard_part = expanded_path.split('*', 1)
            base_dir = Path(base_part.rstrip('\\').rstrip('/'))

            # Get the filename after the wildcard
            if wildcard_part:
                target_filename = Path(wildcard_part.lstrip('\\').lstrip('/')).name
            else:
                # Wildcard at end means apply to all subdirs
                target_filename = None
        else:
            # apply_to_all_subfolders flag
            path = Path(expanded_path)
            base_dir = path.parent
            target_filename = path.name

        if not base_dir.exists():
            logger.warning(f"Base directory does not exist: {base_dir}")
            result["errors"].append(f"Directory not found: {base_dir}")
            return

        # Find the preset content
        preset_content = None
        if target_filename:
            preset_content = file_content_map.get(target_filename)
            if not preset_content:
                # Try to find by any matching file
                for filename, content in file_content_map.items():
                    if filename == target_filename or filename.endswith(Path(target_filename).suffix):
                        preset_content = content
                        target_filename = filename
                        break

        if not preset_content and target_filename:
            result["errors"].append(f"No preset file found for wildcard path: {target_filename}")
            return

        # Find all subdirectories and apply
        applied_count = 0
        for subdir in base_dir.iterdir():
            if subdir.is_dir():
                if target_filename:
                    target_path = subdir / target_filename
                else:
                    # No specific filename, skip
                    continue

                # Create backup if file exists
                if create_backup and target_path.exists():
                    backup_path = self.backup_service.create_backup(game_short_name, target_path)
                    if backup_path:
                        result["backups_created"].append(str(backup_path))

                # Ensure directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write preset file
                try:
                    with open(target_path, 'wb') as f:
                        f.write(preset_content)
                    result["files_applied"].append(str(target_path))
                    logger.info(f"Applied preset to wildcard target: {target_path}")
                    applied_count += 1
                except Exception as e:
                    result["errors"].append(f"Failed to write {target_path}: {str(e)}")

        if applied_count == 0:
            logger.warning(f"No subdirectories found for wildcard path: {config_path}")

    def apply_preset(
        self,
        game_short_name: str,
        preset_level: str,
        files: List[Dict[str, Any]],
        config_files: List[Dict[str, Any]],
        create_backup: bool = True,
        process_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply a preset to the local system

        Args:
            game_short_name: Game identifier
            preset_level: Preset level being applied
            files: List of file dictionaries with content (base64 encoded)
            config_files: List of config file definitions from game metadata
            create_backup: Whether to backup existing configs
            process_name: Optional game process name to kill before applying preset

        Returns:
            Result dictionary
        """
        result = {
            "success": True,
            "game": game_short_name,
            "preset_level": preset_level,
            "files_applied": [],
            "backups_created": [],
            "errors": [],
            "game_killed": False
        }

        try:
            # Kill game process before applying preset if specified
            if process_name:
                logger.info(f"Killing game process before preset apply: {process_name}")
                kill_result = kill_process(process_name)
                if kill_result.get("killed"):
                    logger.info(f"Game process '{process_name}' was terminated")
                    result["game_killed"] = True
                elif kill_result.get("success"):
                    logger.debug(f"Game process '{process_name}' was not running")
                else:
                    logger.warning(f"Failed to kill game process: {kill_result.get('error')}")

            # Create mapping of filename to content
            file_content_map = {}
            for file_data in files:
                filename = file_data.get('filename')
                content_b64 = file_data.get('content')
                if filename and content_b64:
                    file_content_map[filename] = base64.b64decode(content_b64)

            # Process each config file
            for config_def in config_files:
                config_path = config_def.get('path', '')
                config_type = config_def.get('type', 'ini')
                apply_to_all_subfolders = config_def.get('apply_to_all_subfolders', False)

                # Handle registry configs
                if config_type == 'registry':
                    logger.info(f"Processing registry config: {config_path}")
                    self._apply_registry_preset(
                        config_path, file_content_map,
                        game_short_name, create_backup, result
                    )
                    continue

                # Handle wildcard paths (e.g., ...SaveGames\*\file.sav)
                if '*' in config_path or apply_to_all_subfolders:
                    self._apply_to_wildcard_path(
                        config_path, config_def, file_content_map,
                        game_short_name, create_backup, result
                    )
                    continue

                # Resolve target path - use search_paths if provided
                search_paths = config_def.get('search_paths')
                config_filename = config_def.get('filename')

                if search_paths and config_filename:
                    # Search multiple locations for standalone apps (e.g., FFXIV benchmark)
                    target_path = self.resolve_search_paths(search_paths, config_filename)
                    if not target_path:
                        result["errors"].append(f"Could not find {config_filename} in any search path")
                        continue
                else:
                    target_path = self.resolve_config_path(config_path)
                    if not target_path:
                        result["errors"].append(f"Could not resolve path: {config_path}")
                        continue

                # Find matching preset file
                target_filename = target_path.name
                preset_content = file_content_map.get(target_filename)

                if not preset_content:
                    # Try to find by extension
                    for filename, content in file_content_map.items():
                        if filename.endswith(target_path.suffix):
                            preset_content = content
                            break

                if not preset_content:
                    result["errors"].append(f"No preset file found for: {target_filename}")
                    continue

                # Create backup if file exists
                if create_backup and target_path.exists():
                    backup_path = self.backup_service.create_backup(game_short_name, target_path)
                    if backup_path:
                        result["backups_created"].append(str(backup_path))

                # Ensure target directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Merge hardware config if needed (e.g., F1 24 preserves CPU/GPU info)
                if config_def.get('preserve_hardware', False):
                    preset_content = self._merge_hardware_config(
                        preset_content, target_path, config_def
                    )

                # Write preset file
                try:
                    with open(target_path, 'wb') as f:
                        f.write(preset_content)
                    result["files_applied"].append(str(target_path))
                    logger.info(f"Applied preset to: {target_path}")
                except Exception as e:
                    result["errors"].append(f"Failed to write {target_path}: {str(e)}")

            # Cleanup old backups
            self.backup_service.cleanup_old_backups(game_short_name)

            # Set success based on whether any files were applied
            if not result["files_applied"] and result["errors"]:
                result["success"] = False

        except Exception as e:
            logger.error(f"Error applying preset: {e}")
            result["success"] = False
            result["errors"].append(str(e))

        return result
