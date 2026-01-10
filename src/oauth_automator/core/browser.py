import os
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    Playwright,
)

from .logging import setup_logger

logger = setup_logger("oauth_automator.browser")


class BrowserManager:
    def __init__(self, session_dir: str = "./auth_session", headless: bool = False):
        from dotenv import load_dotenv
        load_dotenv()

        custom_profile = os.getenv("BROWSER_PROFILE_PATH", "").strip()
        if custom_profile and Path(custom_profile).exists():
            self.session_dir = Path(custom_profile).absolute()
            self.using_custom_profile = True
            logger.info(f"Using custom browser profile: {self.session_dir}")
        else:
            self.session_dir = Path(session_dir).absolute()
            self.using_custom_profile = False

        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None

    def _find_browser_executable(self) -> Optional[str]:
        env_executable = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
        if env_executable and os.path.exists(env_executable):
            logger.info(f"Using configured browser: {env_executable}")
            return env_executable

        common_paths = [
            "/usr/bin/brave-browser",
            "/usr/bin/google-chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ]

        for path in common_paths:
            if os.path.exists(path):
                logger.info(f"Using system browser: {path}")
                return path

        logger.info("Using Playwright's bundled Chromium")
        return None

    def _check_browser_running(self) -> bool:
        lock_file = self.session_dir / "SingletonLock"
        if lock_file.exists():
            if lock_file.is_symlink():
                try:
                    target = os.readlink(str(lock_file))
                    pid = int(target.split("-")[-1])
                    os.kill(pid, 0)
                    return True
                except (ValueError, OSError):
                    return False
            return True
        return False

    def _cleanup_locks(self):
        if self.using_custom_profile:
            if self._check_browser_running():
                raise RuntimeError(
                    f"❌ Your browser is currently running with this profile!\n"
                    f"   Please close Brave/Chrome completely before running this script.\n"
                    f"   Profile: {self.session_dir}"
                )
            return

        lock_file = self.session_dir / "SingletonLock"
        if lock_file.exists():
            logger.warning(f"Removing stale browser lock file: {lock_file}")
            try:
                lock_file.unlink()
            except OSError as e:
                logger.warning(f"Could not remove lock file: {e}")

    def start(self) -> Page:
        self.playwright = sync_playwright().start()
        executable = self._find_browser_executable()

        self._cleanup_locks()
        if not self.using_custom_profile:
            self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Launching browser with profile: {self.session_dir}")

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir),
            executable_path=executable,
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            slow_mo=50,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
            ],
        )

        return self.context.pages[0] if self.context.pages else self.context.new_page()

    def close(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
