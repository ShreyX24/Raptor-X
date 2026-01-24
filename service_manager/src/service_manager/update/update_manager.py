"""
Update Manager - Handles git pull and service updates for RPX.
"""
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RepoConfig:
    """Configuration for a git repository"""
    name: str
    path: Path
    branch: str
    remote: str = "origin"


@dataclass
class UpdateResult:
    """Result of an update operation"""
    repo: str
    success: bool
    old_commit: str
    new_commit: str
    message: str
    changed_files: List[str] = field(default_factory=list)


class UpdateManager:
    """
    Manages updates for RPX repositories.

    Handles:
    - Checking for updates (git fetch + compare)
    - Pulling updates (git pull)
    - Reinstalling Python packages (pip install -e .)
    - Notifying SUTs of available updates
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.repos = self._configure_repos()
        self.services_to_reinstall = self._configure_services()
        self._progress_callback: Optional[Callable[[str, int, int], None]] = None

    def _configure_repos(self) -> List[RepoConfig]:
        """Configure repositories to update"""
        return [
            RepoConfig(
                name="RPX",
                path=self.base_dir,
                branch="master"
            ),
            RepoConfig(
                name="preset-manager",
                path=self.base_dir / "preset-manager",
                branch="main"
            ),
            RepoConfig(
                name="omniparser",
                path=self.base_dir / "Omniparser server",
                branch="main"
            ),
        ]

    def _configure_services(self) -> List[Path]:
        """Configure services to reinstall after update"""
        return [
            self.base_dir / "rpx-core",
            self.base_dir / "sut_client",
            self.base_dir / "sut_discovery_service",
            self.base_dir / "queue_service",
            self.base_dir / "preset-manager",
            self.base_dir / "service_manager",
        ]

    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """
        Set callback for progress updates.

        Callback signature: (message: str, current: int, total: int)
        """
        self._progress_callback = callback

    def _emit_progress(self, message: str, current: int, total: int):
        """Emit progress update"""
        logger.info(f"Progress: {message} ({current}/{total})")
        if self._progress_callback:
            self._progress_callback(message, current, total)

    def _run_git_command(
        self,
        args: List[str],
        cwd: Path,
        timeout: int = 60
    ) -> Tuple[bool, str, str]:
        """
        Run a git command and return (success, stdout, stderr).
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except FileNotFoundError:
            return False, "", "git not found in PATH"
        except Exception as e:
            return False, "", str(e)

    def get_current_commit(self, repo_path: Path) -> str:
        """Get current commit hash (short)"""
        success, stdout, _ = self._run_git_command(
            ["rev-parse", "--short", "HEAD"],
            repo_path
        )
        return stdout if success else "unknown"

    def get_commit_message(self, repo_path: Path, commit: str = "HEAD") -> str:
        """Get commit message for a commit"""
        success, stdout, _ = self._run_git_command(
            ["log", "-1", "--format=%s", commit],
            repo_path
        )
        return stdout if success else ""

    def has_dirty_state(self, repo_path: Path) -> bool:
        """Check if repo has uncommitted changes"""
        success, stdout, _ = self._run_git_command(
            ["status", "--porcelain"],
            repo_path
        )
        if not success:
            return True  # Assume dirty if can't check
        return bool(stdout)

    def stash_changes(self, repo_path: Path) -> bool:
        """Stash any uncommitted changes"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        success, _, stderr = self._run_git_command(
            ["stash", "push", "-m", f"Auto-stash before update {timestamp}"],
            repo_path
        )
        if not success:
            logger.warning(f"Failed to stash changes: {stderr}")
        return success

    def check_for_updates(self) -> Dict[str, Tuple[str, str, str]]:
        """
        Check if updates are available without pulling.

        Returns:
            Dict of {repo_name: (local_commit, remote_commit, commit_message)}
            Only repos with available updates are included.
        """
        updates = {}

        for i, repo in enumerate(self.repos):
            self._emit_progress(f"Checking {repo.name}...", i, len(self.repos))

            if not repo.path.exists():
                logger.warning(f"Repo path does not exist: {repo.path}")
                continue

            # Fetch without merging
            success, _, stderr = self._run_git_command(
                ["fetch", repo.remote],
                repo.path,
                timeout=30
            )

            if not success:
                logger.error(f"Failed to fetch {repo.name}: {stderr}")
                continue

            # Get local HEAD
            local = self.get_current_commit(repo.path)

            # Get remote HEAD
            success, remote, _ = self._run_git_command(
                ["rev-parse", "--short", f"{repo.remote}/{repo.branch}"],
                repo.path
            )

            if not success:
                logger.error(f"Failed to get remote HEAD for {repo.name}")
                continue

            if local != remote:
                # Get the commit message of the remote HEAD
                success, message, _ = self._run_git_command(
                    ["log", "-1", "--format=%s", f"{repo.remote}/{repo.branch}"],
                    repo.path
                )
                updates[repo.name] = (local, remote, message if success else "")
                logger.info(f"Update available for {repo.name}: {local} -> {remote}")

        self._emit_progress("Check complete", len(self.repos), len(self.repos))
        return updates

    def pull_repo(self, repo: RepoConfig) -> UpdateResult:
        """Pull updates for a single repository"""
        old_commit = self.get_current_commit(repo.path)

        # Check for dirty state
        if self.has_dirty_state(repo.path):
            logger.warning(f"{repo.name} has uncommitted changes, stashing...")
            self.stash_changes(repo.path)

        # Pull with rebase
        success, stdout, stderr = self._run_git_command(
            ["pull", repo.remote, repo.branch, "--rebase"],
            repo.path,
            timeout=120
        )

        if not success:
            return UpdateResult(
                repo=repo.name,
                success=False,
                old_commit=old_commit,
                new_commit=old_commit,
                message=f"Pull failed: {stderr}",
                changed_files=[]
            )

        new_commit = self.get_current_commit(repo.path)

        # Get changed files
        if old_commit != new_commit:
            success, changed, _ = self._run_git_command(
                ["diff", "--name-only", old_commit, new_commit],
                repo.path
            )
            changed_files = changed.split('\n') if success and changed else []
        else:
            changed_files = []

        return UpdateResult(
            repo=repo.name,
            success=True,
            old_commit=old_commit,
            new_commit=new_commit,
            message=stdout or "Up to date",
            changed_files=changed_files
        )

    def update_all(self) -> List[UpdateResult]:
        """Update all repositories"""
        results = []
        total = len(self.repos)

        for i, repo in enumerate(self.repos):
            self._emit_progress(f"Updating {repo.name}...", i, total)

            if not repo.path.exists():
                results.append(UpdateResult(
                    repo=repo.name,
                    success=False,
                    old_commit="unknown",
                    new_commit="unknown",
                    message=f"Path does not exist: {repo.path}"
                ))
                continue

            result = self.pull_repo(repo)
            results.append(result)
            logger.info(f"Updated {repo.name}: {result.old_commit} -> {result.new_commit}")

        self._emit_progress("Pull complete", total, total)
        return results

    def reinstall_services(self) -> Tuple[bool, List[str]]:
        """
        Run pip install -e . for each service.

        Returns:
            (all_success, list of error messages)
        """
        errors = []
        total = len(self.services_to_reinstall)

        for i, service_dir in enumerate(self.services_to_reinstall):
            pyproject = service_dir / "pyproject.toml"

            if not pyproject.exists():
                logger.debug(f"Skipping {service_dir.name}: no pyproject.toml")
                continue

            self._emit_progress(f"Installing {service_dir.name}...", i, total)

            try:
                result = subprocess.run(
                    ["pip", "install", "-e", "."],
                    cwd=str(service_dir),
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode != 0:
                    error_msg = f"{service_dir.name}: {result.stderr[:200]}"
                    errors.append(error_msg)
                    logger.error(f"Failed to install {service_dir.name}: {result.stderr}")
                else:
                    logger.info(f"Installed {service_dir.name}")

            except subprocess.TimeoutExpired:
                errors.append(f"{service_dir.name}: Installation timed out")
            except Exception as e:
                errors.append(f"{service_dir.name}: {str(e)}")

        self._emit_progress("Installation complete", total, total)
        return len(errors) == 0, errors

    def get_version_info(self) -> Dict[str, str]:
        """
        Get current version info for all repos.

        Returns:
            Dict with repo names as keys and commit hashes as values.
        """
        info = {
            "updated_at": datetime.now().isoformat(),
        }

        for repo in self.repos:
            if repo.path.exists():
                info[repo.name] = self.get_current_commit(repo.path)
            else:
                info[repo.name] = "not found"

        return info

    def notify_suts(self, master_ip: str) -> Tuple[bool, str]:
        """
        Notify connected SUTs about the update via SUT Discovery Service.

        Args:
            master_ip: IP address of the master machine

        Returns:
            (success, message)
        """
        import requests

        version_info = self.get_version_info()
        version_info["master_ip"] = master_ip

        try:
            response = requests.post(
                "http://localhost:5001/api/suts/broadcast-update",
                json=version_info,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                notified = data.get("notified", 0)
                return True, f"Notified {notified} SUT(s)"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"

        except requests.exceptions.ConnectionError:
            return False, "SUT Discovery Service not running"
        except requests.exceptions.Timeout:
            return False, "Request timed out"
        except Exception as e:
            return False, str(e)

    def get_local_ip(self) -> str:
        """Get local IP address for SUT notification"""
        import socket
        try:
            # Create a socket and connect to an external address
            # This doesn't actually send data, just determines local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
