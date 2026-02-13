#!/usr/bin/env python3
"""
RPX (Raptor X) - Standalone Setup Script
Replaces setup.bat with a cross-platform, interactive Python installer.
Uses ONLY the Python standard library (runs before dependencies are installed).
"""

import sys
import os
import re
import json
import shutil
import ctypes
import zipfile
import argparse
import threading
import time
import subprocess
import http.cookiejar
import urllib.request
import urllib.error
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

REPO_URL = "https://github.com/ShreyX24/RP-X-temp.git"
REPO_NAME = "RPX"
GDRIVE_FILE_ID = "1Otyc6swsZkzNyDHdPvPIXbyCky6QhNkg"

PIP_SERVICES = [
    # (directory, display_label, cli_command)
    ("rpx-core", "RPX Backend", "gemma"),
    ("sut_discovery_service", "SUT Discovery", "sut-discovery"),
    ("queue_service", "Queue Service", "queue-service"),
    ("service_manager", "Service Manager", "rpx-manager"),
    ("sut_client", "SUT Client", "sut-client"),
    ("preset-manager", "Preset Manager", "preset-manager"),
]

NPM_FRONTENDS = [
    ("rpx-core/admin", "RPX Frontend"),
    ("preset-manager/admin", "Preset Manager Frontend"),
]

SUBMODULE_FALLBACKS = {
    "omniparser-server": "https://github.com/YpS-YpS/OmniLocal.git",
    "preset-manager": "https://github.com/ShreyX24/preset-manager.git",
}

GRADIENT_COLORS = [93, 135, 141, 183, 189, 231]
BANNER_LINES = [
    "\u2588\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557     \u2588\u2588\u2557  \u2588\u2588\u2557",
    "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557    \u255a\u2588\u2588\u2557\u2588\u2588\u2554\u255d",
    "\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d   \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d     \u255a\u2588\u2588\u2588\u2554\u255d",
    "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2550\u255d    \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557     \u2588\u2588\u2554\u2588\u2588\u2557",
    "\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551        \u2588\u2588\u2551   \u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551  \u2588\u2588\u2551    \u2588\u2588\u2554\u255d \u2588\u2588\u2557",
    "\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d        \u255a\u2550\u255d    \u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u255d  \u255a\u2550\u255d    \u255a\u2550\u255d  \u255a\u2550\u255d",
]
BANNER_ASCII = [
    " ____   _    ____ _____ ___  ____    __  __",
    "|  _ \\ / \\  |  _ \\_   _/ _ \\|  _ \\   \\ \\/ /",
    "| |_) / _ \\ | |_) || || | | | |_) |   \\  / ",
    "|  _ < ___ \\|  __/ | || |_| |  _ <    /  \\ ",
    "|_| \\_\\_/ \\_\\_|    |_| \\___/|_| \\_\\  /_/\\_\\",
]
RESET = "\033[0m"


# ── Colors & Output Helpers ──────────────────────────────────────────────────

class Colors:
    """ANSI color helpers with Windows VT100 enable."""

    _enabled = False

    @staticmethod
    def enable():
        if Colors._enabled:
            return
        Colors._enabled = True
        if sys.platform == "win32":
            try:
                k32 = ctypes.windll.kernel32
                h = k32.GetStdHandle(-11)
                mode = ctypes.c_ulong()
                k32.GetConsoleMode(h, ctypes.byref(mode))
                k32.SetConsoleMode(h, mode.value | 0x0004)
            except Exception:
                pass

    @staticmethod
    def fg256(code: int) -> str:
        return f"\033[38;5;{code}m"

    @staticmethod
    def bold(text: str) -> str:
        return f"\033[1m{text}{RESET}"

    @staticmethod
    def green(text: str) -> str:
        return f"\033[92m{text}{RESET}"

    @staticmethod
    def red(text: str) -> str:
        return f"\033[91m{text}{RESET}"

    @staticmethod
    def yellow(text: str) -> str:
        return f"\033[93m{text}{RESET}"

    @staticmethod
    def cyan(text: str) -> str:
        return f"\033[96m{text}{RESET}"

    @staticmethod
    def dim(text: str) -> str:
        return f"\033[90m{text}{RESET}"


def print_banner(pin: bool = True):
    """Print RAPTOR X block-character banner with purple-to-white gradient.

    Args:
        pin: If True, pin the banner to the top of the console using
             ANSI scroll regions (DECSTBM) so setup output scrolls beneath it.
    """
    # Choose banner: try Unicode block chars, fall back to ASCII
    banner = BANNER_LINES
    try:
        BANNER_LINES[0].encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        banner = BANNER_ASCII

    # Banner occupies: 1 blank + len(banner) art + 1 blank + 1 subtitle + 1 blank
    banner_height = 1 + len(banner) + 1 + 1 + 1

    if pin:
        # Clear screen and move cursor to top-left
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    print()  # blank line before banner
    for i, line in enumerate(banner):
        c = GRADIENT_COLORS[i] if i < len(GRADIENT_COLORS) else 231
        try:
            print(f"{Colors.fg256(c)}{line}{RESET}")
        except UnicodeEncodeError:
            print(f"{Colors.fg256(c)}{line.encode('ascii', 'replace').decode()}{RESET}")
    subtitle = "Setup Script"
    pad = max(0, (len(banner[0]) - len(subtitle)) // 2)
    print(f"\n\033[97m{' ' * pad}{subtitle}{RESET}")
    print()

    if pin:
        _pin_banner(banner_height)


def _pin_banner(banner_height: int):
    """Pin the banner by setting an ANSI scroll region below it.

    Uses DECSTBM (Set Top and Bottom Margins) to confine all subsequent
    scrolling to the area below the banner. Supported on Windows 10+
    console and Windows Terminal.
    """
    try:
        _, rows = shutil.get_terminal_size()
        # Set scroll region: row after banner -> bottom of terminal
        # DECSTBM: ESC [ <top> ; <bottom> r
        sys.stdout.write(f"\033[{banner_height + 1};{rows}r")
        # Move cursor into the scroll region
        sys.stdout.write(f"\033[{banner_height + 1};1H")
        sys.stdout.flush()
    except Exception:
        pass  # Fall back to normal scrolling if anything goes wrong


def _reset_scroll_region():
    """Reset DECSTBM scroll region to full terminal (removes banner pinning)."""
    try:
        sys.stdout.write("\033[r")  # Reset scroll region to full window
        sys.stdout.flush()
    except Exception:
        pass


def step_header(num: int, total: int, title: str):
    print(f"\n{Colors.cyan(f'[{num}/{total}]')} {Colors.bold(title)}")
    print(Colors.dim("-" * 60))


def ok(msg: str):
    print(f"  {Colors.green('[OK]')} {msg}")


def warn(msg: str):
    print(f"  {Colors.yellow('[WARN]')} {msg}")


def fail(msg: str):
    print(f"  {Colors.red('[FAIL]')} {msg}")


def run(cmd: list, cwd=None, timeout=600, check=False) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing output."""
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        timeout=timeout, check=check,
    )


# ── Progress Indicators ─────────────────────────────────────────────────────

class Spinner:
    """Animated spinner (/, -, \\, |) with elapsed time for long operations."""

    FRAMES = ['/', '-', '\\', '|']

    def __init__(self, message: str):
        self.message = message
        self._running = False
        self._thread = None
        self._frame = 0
        self._start_time = 0.0

    def start(self):
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def _animate(self):
        while self._running:
            f = self.FRAMES[self._frame % 4]
            elapsed = time.time() - self._start_time
            sys.stdout.write(
                f"\r  [{Colors.cyan(f)}] {self.message} "
                f"{Colors.dim(f'({elapsed:.0f}s)')}\033[K"
            )
            sys.stdout.flush()
            self._frame += 1
            time.sleep(0.15)

    def stop(self, success: bool = True, detail: str = ""):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        status = Colors.green('[OK]') if success else Colors.red('[FAIL]')
        line = f"\r  {status} {self.message}"
        if detail:
            line += f" {Colors.dim(f'({detail})')}"
        sys.stdout.write(f"{line}\033[K\n")
        sys.stdout.flush()


class ProgressBar:
    """Colored gradient progress bar for tracked operations (downloads, extractions)."""

    def __init__(self, total: int, width: int = 35):
        self.total = max(total, 1)
        self.width = width
        self.current = 0
        self._start_time = time.time()

    def update(self, amount: int):
        self.current = min(self.current + amount, self.total)
        self._draw()

    def set(self, value: int):
        self.current = min(value, self.total)
        self._draw()

    def _draw(self):
        pct = self.current / self.total
        filled = int(self.width * pct)

        # Build gradient-colored bar
        bar = ""
        for i in range(filled):
            ci = int(i / max(self.width - 1, 1) * (len(GRADIENT_COLORS) - 1))
            bar += f"{Colors.fg256(GRADIENT_COLORS[ci])}\u2588"
        bar += f"{RESET}\u2591" * (self.width - filled)

        done_mb = self.current / (1024 * 1024)
        total_mb = self.total / (1024 * 1024)
        elapsed = time.time() - self._start_time
        speed = self.current / max(elapsed, 0.001) / (1024 * 1024)

        info = f"({done_mb:.0f}/{total_mb:.0f} MB"
        if speed > 0.1 and pct < 1.0:
            info += f", {speed:.1f} MB/s"
        info += ")"

        sys.stdout.write(f"\r  {bar} {pct * 100:5.1f}% {Colors.dim(info)}\033[K")
        sys.stdout.flush()

    def finish(self):
        self.current = self.total
        self._draw()
        print()


def run_live(cmd: list, label: str, cwd=None, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a subprocess with animated spinner, return CompletedProcess."""
    spinner = Spinner(label)
    spinner.start()
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            spinner.stop(success=True)
        else:
            err_line = ""
            if result.stderr:
                err_line = result.stderr.strip().split('\n')[0][:100]
            spinner.stop(success=False, detail=err_line)
        return result
    except subprocess.TimeoutExpired:
        spinner.stop(success=False, detail="timed out")
        return subprocess.CompletedProcess(cmd, -1, "", "Timeout")
    except FileNotFoundError:
        spinner.stop(success=False, detail=f"{cmd[0]} not found")
        return subprocess.CompletedProcess(cmd, -1, "", f"Command not found: {cmd[0]}")
    except Exception as e:
        spinner.stop(success=False, detail=str(e)[:80])
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


def get_npm_cmd() -> list:
    """Get the npm command, resolving .cmd extension on Windows."""
    if sys.platform == "win32":
        npm = shutil.which("npm")
        if npm:
            return [npm]
        return ["npm.cmd"]
    return ["npm"]


# ── GitManager ───────────────────────────────────────────────────────────────

class GitManager:
    """Clone, fetch, branch selection, checkout, submodule init."""

    def __init__(self, root: Path):
        self.root = root

    def clone_or_detect(self) -> bool:
        """Clone repo or detect existing checkout. Returns True on success."""
        git_dir = self.root / ".git"
        marker = self.root / "rpx-core"
        if git_dir.exists() and marker.exists():
            ok(f"Existing repo detected at {self.root}")
            return True

        # Check parent for RPX subfolder
        child = self.root.parent / REPO_NAME
        if (child / "rpx-core").exists():
            self.root = child
            ok(f"Found existing repo at {child}")
            return True

        r = run_live(
            ["git", "clone", REPO_URL, REPO_NAME],
            "Cloning repository",
            cwd=self.root.parent,
        )
        if r.returncode != 0:
            return False
        self.root = self.root.parent / REPO_NAME
        return True

    def fetch_and_select_branch(self) -> bool:
        """Fetch all remotes and let user pick a branch interactively."""
        run_live(
            ["git", "fetch", "--all", "--prune"],
            "Fetching remote branches",
            cwd=self.root,
        )

        r = run(
            ["git", "for-each-ref", "--sort=-committerdate",
             "refs/remotes/origin/", "--format=%(refname:short) %(committerdate:short)"],
            cwd=self.root,
        )
        branches = []
        for line in r.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if not parts:
                continue
            raw = parts[0]
            if raw == "origin/HEAD":
                continue
            name = raw.replace("origin/", "", 1)
            date = parts[1] if len(parts) > 1 else ""
            branches.append((name, date))

        if not branches:
            warn("No remote branches found")
            return False

        print()
        print("  Available branches (sorted by most recent):")
        for i, (name, date) in enumerate(branches[:9], 1):
            print(f"    [{i}] {name}  {Colors.dim(f'({date})')}")
        if len(branches) > 9:
            print(f"    ... and {len(branches)} total branches (showing top 9)")

        choice_str = input(f"\n  Select branch number [1]: ").strip() or "1"
        try:
            idx = int(choice_str) - 1
            if idx < 0 or idx >= len(branches):
                raise ValueError
        except ValueError:
            warn("Invalid selection, defaulting to branch 1")
            idx = 0

        branch = branches[idx][0]
        print(f"  Switching to: {Colors.bold(branch)}")
        r = run_live(
            ["git", "checkout", branch],
            f"Checking out {branch}",
            cwd=self.root,
        )
        if r.returncode != 0:
            warn(f"Checkout issues: {r.stderr.strip()[:100]}")
        r = run_live(
            ["git", "pull", "origin", branch],
            "Pulling latest changes",
            cwd=self.root,
        )
        if r.returncode != 0:
            warn(f"Pull issues: {r.stderr.strip()[:100]}")
        else:
            ok(f"On branch {branch}, up to date")
        return True

    def init_submodules(self) -> bool:
        """Init/update submodules with fallback cloning."""
        run_live(
            ["git", "submodule", "init"],
            "Initializing submodules",
            cwd=self.root,
        )
        run_live(
            ["git", "submodule", "update", "--recursive"],
            "Updating submodules",
            cwd=self.root,
        )

        for name, url in SUBMODULE_FALLBACKS.items():
            target = self.root / name
            git_check = target / ".git"
            if not git_check.exists():
                r = run_live(
                    ["git", "clone", url, name],
                    f"Cloning fallback: {name}",
                    cwd=self.root,
                )
                if r.returncode != 0:
                    warn(f"Failed to clone {name}")
            else:
                ok(f"Submodule {name} present")
        return True


# ── WeightsDownloader ────────────────────────────────────────────────────────

class WeightsDownloader:
    """Download OmniParser model weights from Google Drive."""

    def __init__(self, root: Path):
        self.root = root
        self.omni_dir = root / "omniparser-server"
        self.weights_zip = self.omni_dir / "weights.zip"
        self.marker = self.omni_dir / "weights" / "icon_detect" / "model.pt"

    def already_present(self) -> bool:
        return self.marker.exists()

    def download(self) -> bool:
        """Download weights via urllib (2-step GDrive) with curl fallback."""
        if self.already_present():
            ok("Weights already exist, skipping download")
            return True

        self.omni_dir.mkdir(parents=True, exist_ok=True)
        print("  Downloading weights from Google Drive (~1.5 GB)...")

        if self._download_urllib() or self._download_curl():
            return self._verify_and_extract()

        fail("Could not download weights")
        print(f"  Download manually: https://drive.google.com/file/d/{GDRIVE_FILE_ID}/view")
        print(f"  Extract weights.zip into: {self.omni_dir}")
        return False

    # -- private helpers --

    def _download_urllib(self) -> bool:
        """Two-step Google Drive download with progress bar."""
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            url1 = f"https://drive.google.com/uc?export=download&id={GDRIVE_FILE_ID}"

            spinner = Spinner("Getting download token")
            spinner.start()
            try:
                resp1 = opener.open(url1, timeout=30)
                html = resp1.read().decode("utf-8", errors="replace")
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                raise

            uuid = ""
            m = re.search(r'name="uuid"\s+value="([^"]+)"', html)
            if m:
                uuid = m.group(1)
            else:
                m = re.search(r"uuid=([a-f0-9-]+)", html)
                if m:
                    uuid = m.group(1)

            url2 = (
                f"https://drive.usercontent.google.com/download"
                f"?id={GDRIVE_FILE_ID}&export=download&confirm=t"
            )
            if uuid:
                url2 += f"&uuid={uuid}"

            resp2 = opener.open(url2, timeout=600)
            total_size = int(resp2.headers.get("Content-Length", 0))

            progress = None
            dl_spinner = None
            if total_size > 0:
                progress = ProgressBar(total_size)
            else:
                dl_spinner = Spinner("Downloading weights (size unknown)")
                dl_spinner.start()

            try:
                with open(self.weights_zip, "wb") as f:
                    while True:
                        chunk = resp2.read(1 << 20)  # 1 MB chunks
                        if not chunk:
                            break
                        f.write(chunk)
                        if progress:
                            progress.update(len(chunk))
            finally:
                if progress:
                    progress.finish()
                if dl_spinner:
                    dl_spinner.stop(success=True)

            return True
        except Exception as e:
            warn(f"urllib download failed: {e}")
            if self.weights_zip.exists():
                self.weights_zip.unlink()
            return False

    def _download_curl(self) -> bool:
        """Fallback: use curl with spinner."""
        if not shutil.which("curl"):
            warn("curl not found, cannot use fallback download")
            return False
        url = (
            f"https://drive.usercontent.google.com/download"
            f"?id={GDRIVE_FILE_ID}&export=download&confirm=t"
        )
        r = run_live(
            ["curl", "-L", "-o", str(self.weights_zip), url],
            "Downloading weights via curl",
            cwd=self.omni_dir,
            timeout=900,
        )
        return r.returncode == 0

    def _verify_and_extract(self) -> bool:
        """Verify file size > 100 MB then extract with progress."""
        if not self.weights_zip.exists():
            fail("weights.zip not found after download")
            return False
        size = self.weights_zip.stat().st_size
        if size < 100_000_000:
            fail(f"Downloaded file too small ({size:,} bytes), likely an error page")
            self.weights_zip.unlink()
            return False
        print(f"  Extracting weights ({size / 1e9:.1f} GB)...")
        try:
            with zipfile.ZipFile(self.weights_zip, "r") as zf:
                members = zf.infolist()
                total = len(members)
                for i, member in enumerate(members):
                    zf.extract(member, self.omni_dir)
                    pct = (i + 1) / total
                    filled = int(35 * pct)
                    bar = ""
                    for j in range(filled):
                        ci = int(j / max(34, 1) * (len(GRADIENT_COLORS) - 1))
                        bar += f"{Colors.fg256(GRADIENT_COLORS[ci])}\u2588"
                    bar += f"{RESET}\u2591" * (35 - filled)
                    sys.stdout.write(
                        f"\r  {bar} {pct * 100:5.1f}% "
                        f"{Colors.dim(f'({i + 1}/{total} files)')}\033[K"
                    )
                    sys.stdout.flush()
                print()
            self.weights_zip.unlink()
            ok("Weights downloaded and extracted")
            return True
        except zipfile.BadZipFile:
            fail("Downloaded file is not a valid zip archive")
            self.weights_zip.unlink()
            return False


# ── DependencyInstaller ──────────────────────────────────────────────────────

class DependencyInstaller:
    """Install pip and npm dependencies."""

    def __init__(self, root: Path):
        self.root = root

    def npm_install(self) -> bool:
        """Run npm install for each frontend with spinner."""
        npm = get_npm_cmd()
        success = True
        for rel, label in NPM_FRONTENDS:
            pkg = self.root / rel / "package.json"
            if not pkg.exists():
                warn(f"{rel}/package.json not found, skipping {label}")
                continue
            r = run_live(
                npm + ["install"],
                f"Installing {label} dependencies",
                cwd=self.root / rel,
                timeout=300,
            )
            if r.returncode != 0:
                success = False
        return success

    def check_python_deps(self) -> list:
        """Check which Python services are already installed.

        Returns list of (dir, label, cli_cmd, is_installed) tuples.
        """
        results = []
        for rel, label, cli in PIP_SERVICES:
            installed = shutil.which(cli) is not None
            results.append((rel, label, cli, installed))
        return results

    def pip_install(self, skip: set = None) -> bool:
        """pip install -e for each Python service with spinner."""
        skip = skip or set()
        success = True
        for rel, label, _cli in PIP_SERVICES:
            if rel in skip:
                ok(f"{label} (skipped)")
                continue
            svc_dir = self.root / rel
            if not (svc_dir / "pyproject.toml").exists() and not (svc_dir / "setup.py").exists() and not (svc_dir / "setup.cfg").exists():
                warn(f"{rel} has no installable config, skipping {label}")
                continue
            r = run_live(
                [sys.executable, "-m", "pip", "install", "-e", str(svc_dir)],
                f"Installing {label}",
                timeout=300,
            )
            if r.returncode != 0:
                success = False
        return success


# ── SSHSetup ─────────────────────────────────────────────────────────────────

class SSHSetup:
    """Install & configure OpenSSH Server on Windows."""

    @staticmethod
    def is_windows() -> bool:
        return sys.platform == "win32"

    @staticmethod
    def _ps(cmd: str, timeout: int = 120):
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )

    def run(self) -> bool:
        if not self.is_windows():
            warn("SSH setup is Windows-only, skipping")
            return True

        steps = [
            ("Check/install OpenSSH Server", self._install_openssh),
            ("Start sshd service", self._start_sshd),
            ("Enable sshd auto-start", self._enable_autostart),
            ("Configure authorized_keys", self._setup_authorized_keys),
        ]
        all_ok = True
        for label, fn in steps:
            try:
                if fn():
                    ok(label)
                else:
                    warn(label)
                    all_ok = False
            except Exception as e:
                warn(f"{label}: {e}")
                all_ok = False
        return all_ok

    def _install_openssh(self) -> bool:
        r = self._ps(
            "Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*' "
            "| Select-Object -ExpandProperty State"
        )
        if "Installed" in r.stdout:
            return True
        r = self._ps(
            "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0",
            timeout=300,
        )
        return r.returncode == 0

    def _start_sshd(self) -> bool:
        r = self._ps("(Get-Service sshd -ErrorAction SilentlyContinue).Status")
        if "Running" in r.stdout:
            return True
        r = self._ps("Start-Service sshd")
        return r.returncode == 0

    def _enable_autostart(self) -> bool:
        r = self._ps("(Get-Service sshd -ErrorAction SilentlyContinue).StartType")
        if "Automatic" in r.stdout:
            return True
        r = self._ps("Set-Service -Name sshd -StartupType 'Automatic'")
        return r.returncode == 0

    def _setup_authorized_keys(self) -> bool:
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        ak = ssh_dir / "authorized_keys"
        if not ak.exists():
            ak.touch()
        # Remove inheritance, grant only current user + Administrators
        try:
            f = str(ak)
            subprocess.run(["icacls", f, "/inheritance:r"], capture_output=True, check=False)
            subprocess.run(["icacls", f, "/grant", f"{os.getlogin()}:F"], capture_output=True, check=False)
            subprocess.run(["icacls", f, "/grant", "Administrators:F"], capture_output=True, check=False)
            subprocess.run(["icacls", f, "/grant", "SYSTEM:F"], capture_output=True, check=False)
        except Exception:
            pass
        return True


# ── NetworkConfigurator ──────────────────────────────────────────────────────

class NetworkConfigurator:
    """Set network profile to Private and create firewall rules for RPX services."""

    FIREWALL_RULES = [
        ("RPX SUT Discovery (TCP)", "TCP", 5001),
        ("RPX SUT Discovery (UDP)", "UDP", 9999),
        ("RPX SUT Client (TCP)", "TCP", 8080),
        ("RPX SSH (TCP)", "TCP", 22),
        ("RPX Frontend (3000)", "TCP", 3000),
        ("Preset Manager Frontend (3001)", "TCP", 3001),
    ]

    @staticmethod
    def _ps(cmd: str, timeout: int = 120):
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )

    def run(self) -> bool:
        if sys.platform != "win32":
            warn("Network setup is Windows-only, skipping")
            return True

        if not ctypes.windll.shell32.IsUserAnAdmin():
            warn("Not running as admin - network/firewall setup requires elevation")
            warn("Re-run setup.bat (it will request admin privileges)")
            return False

        steps = [
            ("Set network profiles to Private", self._set_private_profile),
            ("Create firewall rules", self._create_firewall_rules),
        ]
        all_ok = True
        for label, fn in steps:
            try:
                if fn():
                    ok(label)
                else:
                    warn(label)
                    all_ok = False
            except Exception as e:
                warn(f"{label}: {e}")
                all_ok = False
        return all_ok

    def _set_private_profile(self) -> bool:
        r = self._ps(
            "Get-NetConnectionProfile | Where-Object {$_.NetworkCategory -eq 'Public'} "
            "| Select-Object -ExpandProperty Name"
        )
        public_ifaces = [line.strip() for line in r.stdout.strip().splitlines() if line.strip()]
        if not public_ifaces:
            ok("All network interfaces already Private/Domain")
            return True

        success = True
        for iface in public_ifaces:
            safe_name = iface.replace("'", "''")
            r = self._ps(
                f"Set-NetConnectionProfile -Name '{safe_name}' -NetworkCategory Private"
            )
            if r.returncode == 0:
                ok(f"Set '{iface}' to Private")
            else:
                warn(f"Failed to set '{iface}' to Private: {r.stderr.strip()}")
                success = False
        return success

    def _create_firewall_rules(self) -> bool:
        success = True
        for name, protocol, port in self.FIREWALL_RULES:
            # Check if rule already exists
            r = self._ps(
                f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue"
            )
            if r.returncode == 0 and name in r.stdout:
                ok(f"Rule '{name}' already exists")
                continue

            r = self._ps(
                f"New-NetFirewallRule -DisplayName '{name}' "
                f"-Direction Inbound -Protocol {protocol} -LocalPort {port} "
                f"-Action Allow -Profile Private,Domain "
                f"-Description 'RPX setup: allow {protocol}/{port}'"
            )
            if r.returncode == 0:
                ok(f"Created rule '{name}' ({protocol}/{port})")
            else:
                warn(f"Failed to create rule '{name}': {r.stderr.strip()}")
                success = False
        return success


# ── SettingsConfigurator ─────────────────────────────────────────────────────

class SettingsConfigurator:
    """Write / merge ~/.rpx/service_manager_config.json."""

    CONFIG_DIR = Path.home() / ".rpx"
    CONFIG_FILE = CONFIG_DIR / "service_manager_config.json"

    def __init__(self, root: Path):
        self.root = root

    def configure(self) -> bool:
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        existing = {}
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        project_dir = self._detect_project_dir()
        omni_dir = ""
        if project_dir:
            candidate = os.path.join(project_dir, "omniparser-server", "omnitool", "omniparserserver")
            if os.path.isdir(candidate):
                omni_dir = candidate

        # Merge: only set values that are empty / missing
        if not existing.get("project_dir"):
            existing["project_dir"] = project_dir or ""
        if not existing.get("omniparser_dir"):
            existing["omniparser_dir"] = omni_dir
        existing.setdefault("version", "1.0")
        existing.setdefault("default_host", "localhost")
        existing.setdefault("services", {})
        existing.setdefault("profiles", {"local": {"description": "All services on localhost", "overrides": {}}})
        existing.setdefault("active_profile", "local")
        existing.setdefault("omniparser_servers", [])
        existing.setdefault("omniparser_instance_count", 0)
        existing.setdefault("steam_account_pairs", [])
        existing.setdefault("steam_login_timeout", 180)
        existing.setdefault("banner_gradient", GRADIENT_COLORS[:])

        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        ok(f"Config written to {self.CONFIG_FILE}")
        if existing.get("project_dir"):
            ok(f"project_dir = {existing['project_dir']}")
        if existing.get("omniparser_dir"):
            ok(f"omniparser_dir = {existing['omniparser_dir']}")
        return True

    def _detect_project_dir(self) -> str:
        """Walk up from CWD looking for .git + rpx-core."""
        d = self.root
        for _ in range(10):
            if (d / ".git").exists() and (d / "rpx-core").exists():
                return str(d)
            parent = d.parent
            if parent == d:
                break
            d = parent
        return ""


# ── RPXSetup Orchestrator ────────────────────────────────────────────────────

class RPXSetup:
    """Orchestrates all setup steps with error isolation and summary."""

    def __init__(self, root: Path, install_only: bool = False):
        self.root = root
        self.install_only = install_only
        self.git = GitManager(root)
        self.results = []  # list of (title, passed) tuples

    def run(self, banner_printed: bool = False):
        Colors.enable()
        if not banner_printed:
            print_banner()
        self._check_prerequisites()

        if self.install_only:
            if not (self.root / "rpx-core").exists():
                fail("Not in RPX directory. Please run from the RPX root folder.")
                fail("Expected to find 'rpx-core' folder.")
                sys.exit(1)
            self._run_install_steps()
        else:
            self._run_full_setup()

        self._print_summary()

    # ── prerequisites ────────────────────────────────────────────────

    def _check_prerequisites(self):
        py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ok(f"Python {py}")

        node = shutil.which("node")
        if node:
            r = run(["node", "--version"])
            ok(f"Node.js {r.stdout.strip()}")
        else:
            fail("Node.js not found. Install from https://nodejs.org/")
            sys.exit(1)

        git = shutil.which("git")
        if git:
            r = run(["git", "--version"])
            ok(f"{r.stdout.strip()}")
        else:
            fail("Git not found. Install from https://git-scm.com/")
            sys.exit(1)

    # ── full setup (10 steps) ────────────────────────────────────────

    def _run_full_setup(self):
        total = 10
        self._step(1, total, "Clone / detect repository", self._do_clone)
        # After clone, root may have changed
        self.root = self.git.root
        self._step(2, total, "Fetch & select branch", self._do_branch)
        self._step(3, total, "Initialize submodules", self._do_submodules)
        self._step(4, total, "Download OmniParser weights", self._do_weights)
        self._run_install_steps(start=5, total=total)

    def _run_install_steps(self, start: int = 1, total: int = 6):
        offset = start - 1
        adj_total = total if total > 6 else 6
        self._step(offset + 1, adj_total, "Network & firewall setup", self._do_network)
        self._step(offset + 2, adj_total, "Install NPM dependencies", self._do_npm)
        self._step(offset + 3, adj_total, "Install Python services (pip -e)", self._do_pip)
        self._step(offset + 4, adj_total, "SSH server setup", self._do_ssh)
        self._step(offset + 5, adj_total, "OmniParser dependencies (optional)", self._do_omni_deps)
        self._step(offset + 6, adj_total, "Configure service manager settings", self._do_settings)

    # ── individual step runners ──────────────────────────────────────

    def _step(self, num: int, total: int, title: str, fn):
        step_header(num, total, title)
        try:
            success = fn()
        except Exception as e:
            fail(f"Unexpected error: {e}")
            success = False
        self.results.append((title, success))

    def _do_clone(self) -> bool:
        return self.git.clone_or_detect()

    def _do_branch(self) -> bool:
        return self.git.fetch_and_select_branch()

    def _do_submodules(self) -> bool:
        return self.git.init_submodules()

    def _do_weights(self) -> bool:
        dl = WeightsDownloader(self.root)
        return dl.download()

    def _do_network(self) -> bool:
        net = NetworkConfigurator()
        return net.run()

    def _do_npm(self) -> bool:
        installer = DependencyInstaller(self.root)
        return installer.npm_install()

    def _do_pip(self) -> bool:
        installer = DependencyInstaller(self.root)

        # Pre-check which services are already installed
        deps = installer.check_python_deps()
        installed_count = sum(1 for _, _, _, inst in deps if inst)

        if installed_count > 0:
            print(f"\n  {Colors.cyan(str(installed_count))}/{len(deps)} Python services already installed:")
            for _rel, label, cli, inst in deps:
                status = Colors.green('\u2713 installed') if inst else Colors.dim('\u2717 not installed')
                print(f"    {status}  {label} ({Colors.dim(cli)})")

            print(f"\n  {Colors.yellow('Note:')} Reinstalling is recommended to keep versions current.")
            choice = input(f"  [R]einstall all (recommended) / [S]kip? [R]: ").strip().lower() or 'r'
            if choice == 's':
                ok("Skipping Python dependency installation")
                return True

        return installer.pip_install()

    def _do_ssh(self) -> bool:
        ssh = SSHSetup()
        return ssh.run()

    def _do_omni_deps(self) -> bool:
        print("  OmniParser requires Python 3.12 + CUDA 12.8 + PyTorch 2.8.0")
        print("  It will install ~2 GB of dependencies + flash-attention wheel.")
        choice = input("  Install OmniParser dependencies? (y/n) [n]: ").strip().lower()
        if choice != "y":
            ok("Skipping OmniParser dependencies")
            return True
        install_bat = self.root / "omniparser-server" / "install.bat"
        if not install_bat.exists():
            warn("omniparser-server/install.bat not found, skipping")
            return False
        r = run_live(
            ["cmd", "/c", str(install_bat)],
            "Installing OmniParser dependencies",
            cwd=self.root / "omniparser-server",
            timeout=600,
        )
        if r.returncode != 0:
            return False
        return True

    def _do_settings(self) -> bool:
        cfg = SettingsConfigurator(self.root)
        return cfg.configure()

    # ── summary ──────────────────────────────────────────────────────

    def _print_summary(self):
        # Reset scroll region so summary is visible in full terminal
        _reset_scroll_region()
        print(f"\n{'=' * 60}")
        print(Colors.bold("  Setup Summary"))
        print(f"{'=' * 60}")
        for title, passed in self.results:
            icon = Colors.green("PASS") if passed else Colors.red("FAIL")
            print(f"  [{icon}] {title}")
        all_passed = all(p for _, p in self.results)
        print()
        if all_passed:
            print(Colors.green("  All steps completed successfully!"))
        else:
            print(Colors.yellow("  Some steps had warnings - review output above."))
        print()


# ── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RPX Setup Script")
    parser.add_argument("--skip-clone", "--install-only", "-s",
                        dest="install_only", action="store_true",
                        help="Skip git operations, install dependencies only")
    args = parser.parse_args()

    Colors.enable()

    install_only = args.install_only
    banner_printed = False

    if not install_only:
        print_banner()
        banner_printed = True
        print("  Select setup mode:")
        print(f"    {Colors.cyan('[1]')} Full setup (clone/update + install)")
        print(f"    {Colors.cyan('[2]')} Install only (skip git operations)")
        print()
        choice = input("  Enter choice (1 or 2) [1]: ").strip() or "1"
        if choice == "2":
            install_only = True

    root = Path.cwd()
    setup = RPXSetup(root, install_only=install_only)
    setup.run(banner_printed=banner_printed)


if __name__ == "__main__":
    main()
