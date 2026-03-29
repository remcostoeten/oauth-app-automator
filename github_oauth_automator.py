#!/usr/bin/env python3
"""
GitHub OAuth App Creator - Production Grade Automation
======================================================
Author: Remco Stoeten
Date: 2025-12-30

This script demonstrates how to automate complex web flows that lack a public API
using Playwright with a persistent browser context.

Key Features:a
- Persistent Authentication: Reuses your browser session (cookies/local storage)
- Robust Selectors: Handles slight UI variations for resilience
- Sudo Mode Support: Detects and handles GitHub's password confirmation prompts
- Browser Reuse: Optionally connects to your installed Brave/Chrome browser
- Clean Architecture: Separates browser management from automation logic

Usage:
    python github_oauth_automator.py --app-name "MyCoolApp" --write-env
"""

import argparse
import logging
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Union

from playwright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    Playwright,
    ElementHandle,
)
import platform
import subprocess
import re
from urllib.parse import urlparse

# Try to import AuditLogger, but don't fail if dependencies missing (e.g. during simple unit tests)
try:
    from github_audit_logger import AuditLogger
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False
    logger = logging.getLogger("auth_automator") 
    # Fallback to avoid breaking if file missing
    class AuditLogger:
        def __init__(self, *args): pass
        def log_credential(self, *args, **kwargs): pass
        def read_log(self): return []


# Configure logging to look nice in the terminal
# Configure logging with custom colors
class LogFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""

    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    dim = "\x1b[2m"

    format_str = "%(asctime)s | %(levelname)-8s | %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: dim + "%(asctime)s" + reset + " | " + "%(message)s",
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


# Setup logger
logger = logging.getLogger("auth_automator")
logger.setLevel(logging.INFO)

# Console handler with custom formatter
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(LogFormatter())
logger.addHandler(ch)


@dataclass
class GitHubSelectors:
    """Centralized configuration for all DOM selectors."""

    # Login & Auth
    LOGIN_INPUT = "input[name='login']"
    LOGGED_IN_META = 'meta[name="user-login"]'

    # Sudo Mode / Re-auth
    PASSKEY_INDICATORS = [
        "text='Passkey'",
        "text='Use passkey'",
        "button:has-text('Use passkey')",
    ]
    PASSWORD_LINK_SELECTORS = [
        "a:has-text('Use your password')",
        "text='Use your password'",
        "a[href*='password']",
    ]
    SUDO_INDICATORS = [
        "text='Confirm password'",
        "text='Confirm user'",
        "input[name='password']",
        "input[type='password']",
    ]
    PASSWORD_INPUT = "input[name='password'], input[type='password']"
    SUBMIT_BUTTONS = [
        'button[type="submit"]',
        'button:has-text("Confirm")',
        'button:has-text("Verify")',
        'input[type="submit"]',
    ]

    # App Creation
    APP_NAME_INPUT = 'input[name="oauth_application[name]"]'
    APP_URL_INPUT = 'input[name="oauth_application[url]"]'
    APP_DESC_INPUT = 'textarea[name="oauth_application[description]"]'
    CALLBACK_URL_INPUT = 'input[name="oauth_application[callback_url]"]'
    REGISTER_BUTTON = 'button:has-text("Register application")'
    CLIENT_ID_DISPLAY = ".listgroup-item code, code"

    # Secret Generation
    GENERATE_SECRET_BUTTONS = [
        'button:has-text("Generate a new client secret")',
        'summary:has-text("Generate a new client secret")',
        "#js-oauth-reg-new-client-secret",
        'input[type="submit"][value*="client secret" i]',
        'a:has-text("Generate a new client secret")',
        'form[action*="secret"] button[type="submit"]',
        'button:has-text("Generate client secret")',
        '[data-confirm]:has-text("Generate")',
    ]

    # App Listings
    APP_LINKS = [
        'a[href*="/settings/applications/"][href*="/"]',
        '.listgroup a[href*="/settings/applications/"]',
        'li a[href*="/settings/applications/"]',
    ]
    NEXT_PAGE_LINK = 'a.next_page, a[rel="next"]'

    # Deletion
    DELETE_BUTTONS = [
        'button:has-text("Delete")',
        'summary:has-text("Delete")',
        'button[type="submit"]:has-text("Delete")',
        'a:has-text("Delete application")',
    ]
    CONFIRM_DELETE_INPUT = 'input[name="verify"], input[aria-label*="confirm"]'
    CONFIRM_DELETE_BUTTONS = [
        'button:has-text(" Delete this OAuth application")',  # GitHub weird spacing sometimes
        'button:has-text("Delete this OAuth application")',
        'button[type="submit"]:has-text("Delete")',
        'button.btn-danger[type="submit"]',
    ]


@dataclass
class OAuthConfig:
    """Type-safe configuration for the OAuth application."""

    name: str
    description: str = "Created via Playwright Automation"
    homepage_url: str = "http://localhost:3000"
    callback_url: str = "http://localhost:3000/api/auth/callback/github"


@dataclass
class OAuthCredentials:
    """The output credentials we want to capture."""

    client_id: str
    client_secret: str
    app_name: str
    app_url: str = ""

    def to_env_string(self) -> str:
        """Returns the credentials formatted for a .env file."""
        return f'''
# GitHub OAuth Credentials ({self.app_name})
GITHUB_CLIENT_ID="{self.client_id}"
GITHUB_CLIENT_SECRET="{self.client_secret}"
'''

    def to_env_string_with_prefix(self, prefix: str = "") -> str:
        """Returns credentials formatted for .env file with optional prefix."""
        key_prefix = f"{prefix}_" if prefix else ""
        return f'''
# GitHub OAuth Credentials ({self.app_name})
{key_prefix}GITHUB_CLIENT_ID="{self.client_id}"
{key_prefix}GITHUB_CLIENT_SECRET="{self.client_secret}"
'''

    def verify(self) -> bool:
        """
        Verify the OAuth credentials by making a test request to GitHub.
        Returns True if credentials appear valid.
        """
        logger.info("🔍 Verifying OAuth credentials...")

        # We can't fully test OAuth without a redirect flow, but we can:
        # 1. Check if the client_id format is valid (Ov23li prefix for OAuth apps)
        # 2. Make a request to the OAuth authorize endpoint to see if it recognizes the client

        if not self.client_id.startswith("Ov23li"):
            logger.warning(
                f"   ⚠️  Client ID has unexpected prefix: {self.client_id[:6]}"
            )
            return False

        if len(self.client_secret) < 30:
            logger.warning(
                f"   ⚠️  Client secret seems too short: {len(self.client_secret)} chars"
            )
            return False

        # Try to hit the OAuth authorize endpoint - if client_id is invalid, GitHub returns an error page
        try:
            test_url = f"https://github.com/login/oauth/authorize?client_id={self.client_id}&response_type=code"
            req = urllib.request.Request(test_url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")

            with urllib.request.urlopen(req, timeout=10) as response:
                # GitHub should redirect (302) or show the auth page (200)
                # An invalid client_id returns 200 but with error content
                if response.status in [200, 302]:
                    # Check if we got redirected to an error page
                    final_url = response.url
                    if "error" in final_url.lower():
                        logger.error(f"   ❌ GitHub returned an error for client_id")
                        return False

                    logger.info("   ✅ Client ID is recognized by GitHub")
                    logger.info("   ✅ Client secret format is valid")
                    logger.info("   ✅ Credentials verified successfully!")
                    return True

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.error(f"   ❌ Client ID not found on GitHub")
                return False
            # Other HTTP errors might be fine (rate limiting, etc.)
            logger.warning(f"   ⚠️  HTTP {e.code} - verification inconclusive")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not verify: {e}")

        # If we can't verify online, at least check the format
        logger.info("   ✅ Credential format looks valid (online verification skipped)")
        return True


class BrowserManager:
    """
    Manages the browser lifecycle, profile persistence, and executable detection.

    This class handles the complexity of:
    1. Finding the right browser (Brave, Chrome, or bundled Chromium)
    2. Managing the persistent user data directory (profile)
    3. Cleaning up lock files if the browser crashed previously
    4. Using custom browser profiles (e.g., your existing Brave session)
    """

    def __init__(self, session_dir: str = "./auth_session", headless: bool = False):
        # Load .env for configuration
        from dotenv import load_dotenv

        load_dotenv()

        # Check if custom profile path is set
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
        """Tries to find a system-installed browser for a more natural experience."""
        # 1. Check env var (set by setup.sh)
        env_executable = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
        if env_executable and os.path.exists(env_executable):
            logger.info(f"Using configured browser: {env_executable}")
            return env_executable

        # 2. Check common paths (fallback)
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
        """Check if a browser is using this profile (SingletonLock exists and is active)."""
        lock_file = self.session_dir / "SingletonLock"
        if lock_file.exists():
            # On Linux, the lock is a symlink to the PID
            if lock_file.is_symlink():
                try:
                    target = os.readlink(str(lock_file))
                    # Format is typically "hostname-pid"
                    pid = int(target.split("-")[-1])
                    # Check if process is still running
                    os.kill(pid, 0)
                    return True  # Process is running
                except (ValueError, OSError):
                    return False  # Process not running, stale lock
            return True  # Lock exists but we can't determine status
        return False

    def _cleanup_locks(self):
        """Removes stale usage locks if the previous session crashed."""
        if self.using_custom_profile:
            # Don't cleanup locks for custom profiles - check if browser is running instead
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

    def _is_missing_playwright_browser_error(self, error: Exception) -> bool:
        """Detect the common case where Playwright is installed but Chromium is not."""
        message = str(error)
        return "Executable doesn't exist" in message and "playwright install" in message

    def _install_playwright_browser(self):
        """
        Ensure Playwright's Chromium binary exists.

        Preferred recovery path:
        1. Reuse an existing global `playwright` CLI if present
        2. Install it via `npm i -g playwright`
        3. Run `playwright install chromium`
        """
        playwright_cli = shutil.which("playwright")
        npm_cli = shutil.which("npm")

        if not playwright_cli:
            if not npm_cli:
                raise RuntimeError(
                    "Playwright Chromium is missing and neither `playwright` nor "
                    "`npm` is available.\n"
                    "Install it manually with:\n"
                    "  npm i -g playwright\n"
                    "  playwright install chromium"
                )

            logger.warning(
                "Playwright CLI not found. Installing it globally with npm..."
            )
            subprocess.run(
                [npm_cli, "i", "-g", "playwright"],
                check=True,
            )
            playwright_cli = shutil.which("playwright")

        if not playwright_cli:
            raise RuntimeError(
                "Installed Playwright CLI could not be found in PATH.\n"
                "Run these commands manually and try again:\n"
                "  npm i -g playwright\n"
                "  playwright install chromium"
            )

        logger.warning("Playwright Chromium is missing. Installing it now...")
        subprocess.run([playwright_cli, "install", "chromium"], check=True)
        logger.info("Playwright Chromium installed successfully")

    def start(self) -> Page:
        """
        Starts the browser with a persistent context.
        Returns the main page object.
        """
        self.playwright = sync_playwright().start()
        executable = self._find_browser_executable()

        # Ensure session directory exists or is valid
        self._cleanup_locks()
        if not self.using_custom_profile:
            self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Launching browser with profile: {self.session_dir}")

        # launch_persistent_context is key here!
        # It allows us to save cookies/session data to disk.
        launch_options = {
            "user_data_dir": str(self.session_dir),
            "executable_path": executable,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 900},
            "slow_mo": 50,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
            ],
        }

        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                **launch_options
            )
        except Exception as e:
            if not executable and self._is_missing_playwright_browser_error(e):
                try:
                    self._install_playwright_browser()
                except subprocess.CalledProcessError as install_error:
                    raise RuntimeError(
                        "Playwright Chromium is missing and automatic installation failed.\n"
                        "Run these commands manually and try again:\n"
                        "  npm i -g playwright\n"
                        "  playwright install chromium"
                    ) from install_error

                self.context = self.playwright.chromium.launch_persistent_context(
                    **launch_options
                )
            else:
                raise

        # Get the first page or create one
        return self.context.pages[0] if self.context.pages else self.context.new_page()

    def close(self):
        """Cleanly shuts down the browser."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()


class GitHubAutomator:
    """
    Encapsulates the business logic for GitHub interaction.
    Functions here correspond to specific high-level tasks on the website.
    """

    def __init__(self, page: Page, password: Optional[str] = None):
        self.page = page
        self.password = password

    def ensure_logged_in(self) -> bool:
        """
        Verifies login status and waits for user input if needed.
        Returns True if logged in, False if timed out.
        """
        self.page.goto("https://github.com/settings/developers")

        # Check specific login indicators
        if "/login" in self.page.url or self.page.query_selector(
            GitHubSelectors.LOGIN_INPUT
        ):
            logger.info(
                "🔐 Authentication required. Please log in via the browser window."
            )

            # Wait for user to perform manual login
            try:
                # Wait for the user-login meta tag which appears on all authenticated pages
                self.page.wait_for_selector(
                    GitHubSelectors.LOGGED_IN_META, timeout=300_000
                )  # 5 min timeout
                logger.info("✅ Login detected!")
                return True
            except Exception:
                logger.error("❌ Login timed out.")
                return False

        logger.info("✅ Already logged in (session restored)")
        return True

    def handle_sudo_mode(self):
        """
        Detects and handles GitHub's 'Sudo Mode' (password re-confirmation).
        This often triggers when accessing sensitive settings like Developer Apps.
        Now also handles the new Passkey UI.
        """
        # Give the page a moment to settle
        time.sleep(1)

        # Check for the new Passkey UI first
        is_passkey = any(
            self.page.query_selector(s) for s in GitHubSelectors.PASSKEY_INDICATORS
        )

        if is_passkey:
            logger.info(
                "🔐 Passkey authentication detected, clicking 'Use your password'..."
            )

            # Click "Use your password" link
            clicked = False
            for selector in GitHubSelectors.PASSWORD_LINK_SELECTORS:
                try:
                    link = self.page.query_selector(selector)
                    if link and link.is_visible():
                        link.click()
                        clicked = True
                        logger.info("   Switched to password authentication")
                        time.sleep(1)  # Wait for form to appear
                        break
                except Exception:
                    continue

            if not clicked:
                logger.warning(
                    "   Could not find 'Use your password' link, please click it manually"
                )

        # Now check for password input (either from passkey fallback or direct sudo mode)
        password_field = self.page.query_selector(GitHubSelectors.PASSWORD_INPUT)

        if password_field and password_field.is_visible():
            if self.password:
                logger.info("🔐 Entering password automatically...")
                password_field.fill(self.password)

                # Try to submit the form
                for selector in GitHubSelectors.SUBMIT_BUTTONS:
                    try:
                        btn = self.page.query_selector(selector)
                        if btn and btn.is_visible():
                            btn.click()
                            logger.info("   Submitted password form")
                            break
                    except Exception:
                        continue

                # Wait for password field to disappear (success indicator)
                try:
                    self.page.wait_for_selector(
                        GitHubSelectors.PASSWORD_INPUT, state="detached", timeout=10_000
                    )
                    logger.info("✅ Sudo mode passed!")
                except:
                    logger.warning(
                        "   Password field still visible, may need manual intervention"
                    )
            else:
                logger.warning("🔐 GitHub Sudo Mode detected (password confirmation).")
                logger.warning(
                    "   No --password provided. Please enter your password in the browser..."
                )

                try:
                    self.page.wait_for_selector(
                        GitHubSelectors.PASSWORD_INPUT,
                        state="detached",
                        timeout=300_000,
                    )
                    logger.info("✅ Sudo mode passed!")
                except:
                    logger.error("❌ Timed out waiting for sudo mode confirmation.")
                    raise TimeoutError("Sudo mode timeout")

    def list_oauth_apps(self) -> List[dict]:
        """
        List all OAuth apps for the current user, handling pagination.
        Returns a list of dicts with 'name', 'client_id', and 'url'.
        """
        logger.info("📋 Fetching OAuth apps list...")
        self.page.goto("https://github.com/settings/developers")
        self.handle_sudo_mode()

        # Wait for the page to load
        time.sleep(2)

        apps = []
        page_num = 1

        while True:
            logger.info(f"   Scanning page {page_num}...")

            # Scrape apps on current page
            found_on_page = 0

            # Method 1: Look for links in the OAuth Apps section
            for selector in GitHubSelectors.APP_LINKS:
                app_elements = self.page.query_selector_all(selector)

                for el in app_elements:
                    href = el.get_attribute("href")
                    if not href:
                        continue

                    # Filter out "new" links and ensure it's an actual app
                    if "/new" in href or href.endswith("/settings/applications"):
                        continue

                    # Must have numeric ID pattern: /settings/applications/12345
                    path_parts = href.split("/")
                    if len(path_parts) >= 4 and path_parts[-1].isdigit():
                        name = el.inner_text().strip()
                        if name and len(name) > 0:
                            app_url = (
                                f"https://github.com{href}"
                                if href.startswith("/")
                                else href
                            )

                            # Avoid duplicates
                            if not any(app["url"] == app_url for app in apps):
                                apps.append(
                                    {
                                        "name": name,
                                        "url": app_url,
                                    }
                                )
                                found_on_page += 1

            logger.info(f"   Found {found_on_page} apps on page {page_num}")

            # Check for pagination "Next" button
            next_btn = self.page.query_selector(GitHubSelectors.NEXT_PAGE_LINK)
            if next_btn and next_btn.is_visible():
                logger.info("   Found next page, navigating...")
                next_btn.click()
                time.sleep(1.5)  # Wait for navigation
                page_num += 1
            else:
                break

        logger.info(f"   Total found: {len(apps)} OAuth app(s)")
        return apps

    def delete_oauth_app(self, app_url: str, app_name: str) -> bool:
        """
        Delete an OAuth app by navigating to its settings page and clicking delete.
        Returns True if successful.
        """
        logger.info(f"🗑️  Deleting OAuth app: {app_name}")

        try:
            # Navigate to the app's settings page
            logger.info(f"   Navigating to {app_url}...")
            # Use domcontentloaded for faster interaction, networkidle might be too strict
            response = self.page.goto(app_url, timeout=20000, wait_until="domcontentloaded")
            if not response:
                logger.warning("   Navigation response was empty, but proceeding...")
            
            # Check if we got redirected to login or sudo mode
            time.sleep(1)
            self.handle_sudo_mode()
            time.sleep(1)

            # Scroll to bottom where delete button usually is
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)

            # Find and click the delete button
            clicked = False
            for selector in GitHubSelectors.DELETE_BUTTONS:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked = True
                        logger.info("   Clicked delete button")
                        time.sleep(1)
                        break
                except Exception:
                    continue

            if not clicked:
                logger.error("   Could not find delete button")
                return False

            # Handle confirmation dialog
            # GitHub usually asks you to type the app name to confirm
            confirmation_input = self.page.query_selector(
                GitHubSelectors.CONFIRM_DELETE_INPUT
            )

            if confirmation_input and confirmation_input.is_visible():
                logger.info("   Entering confirmation...")
                confirmation_input.fill(app_name)
                time.sleep(0.5)

                # Click the final confirm button
                for selector in GitHubSelectors.CONFIRM_DELETE_BUTTONS:
                    try:
                        confirm_btn = self.page.query_selector(selector)
                        if confirm_btn and confirm_btn.is_visible():
                            confirm_btn.click()
                            logger.info("   Confirmed deletion")
                            # Wait for navigation explicitly
                            try:
                                self.page.wait_for_url(
                                    "**/settings/developers", timeout=10000
                                )
                                logger.info("   ✅ App deleted successfully")
                                return True
                            except:
                                logger.warning(
                                    "   ⚠️ Timed out waiting for redirection, but deletion may have succeeded"
                                )
                                return True
                            break
                    except Exception:
                        continue

            # Fallback verification
            if "settings/developers" in self.page.url:
                logger.info("   ✅ App deleted successfully")
                return True
            else:
                logger.warning("   Deletion may not have completed")
                return False

        except Exception as e:
            logger.error(f"   ❌ Deletion failed: {e}")
            return False

    def create_oauth_app(self, config: OAuthConfig) -> OAuthCredentials:
        """
        Navigates to the creation page and fills out the form.
        """
        logger.info(f"📝 Navigate to create app: {config.name}")
        self.page.goto("https://github.com/settings/applications/new")

        self.handle_sudo_mode()

        self.handle_sudo_mode()

        # Robustly wait for the form
        self.page.wait_for_selector(GitHubSelectors.APP_NAME_INPUT, timeout=15000)

        while True:
            logger.info("   Filling form details...")
            self.page.fill(GitHubSelectors.APP_NAME_INPUT, config.name)
            self.page.fill(GitHubSelectors.APP_URL_INPUT, config.homepage_url)
            self.page.fill(GitHubSelectors.APP_DESC_INPUT, config.description)
            self.page.fill(GitHubSelectors.CALLBACK_URL_INPUT, config.callback_url)

            logger.info("   Submitting form...")
            self.page.click(GitHubSelectors.REGISTER_BUTTON)

            # Wait for EITHER success redirect OR error message
            # Success: URL changes to /settings/applications/...
            # Error: Stays on /new and shows flash error or input-validation-error
            
            try:
                # Polling for success or error
                for _ in range(10): # Try for ~5 seconds
                    current_url = self.page.url
                    if "/settings/applications/" in current_url and "/new" not in current_url:
                        break # Success!
                    
                    # Check for errors
                    error_el = self.page.query_selector('.flash-error, .error, #js-flash-container .flash-error')
                    if error_el and error_el.is_visible():
                        error_text = error_el.inner_text().strip()
                        if "already taken" in error_text.lower() or "name" in error_text.lower():
                            logger.warning(f"⚠️  Name '{config.name}' is already taken.")
                            print("\n\033[91m❌ Error: App name is already taken on GitHub.\033[0m")
                            new_name = input("\033[94m➤\033[0m Enter a different app name: ").strip()
                            if new_name:
                                config.name = new_name
                                # Clear the input and retry loop
                                self.page.fill(GitHubSelectors.APP_NAME_INPUT, "")
                                break # Break inner check loop to retry outer submission loop
                        else:
                             # Some other error?
                             logger.warning(f"⚠️  GitHub Error: {error_text}")
                    
                    time.sleep(0.5)
                else: 
                     # If loop finishes without break, we might be stuck or slow
                     if "/settings/applications/" in self.page.url and "/new" not in self.page.url:
                         break # Success just in time
                     
                     # If we are here, we looped 10 times and didn't see success or explicit error. 
                     # Check one last time for success, otherwise assume maybe network/timeout or silent fail
                     pass

                # Inner break above breaks the polling loop, but we need to check if we succeeded
                if "/settings/applications/" in self.page.url and "/new" not in self.page.url:
                    break # Break outer submission loop - SUCCESS
                    
            except Exception as e:
                logger.error(f"Error checking submission: {e}")
                # Don't break, maybe try again or manual intervention?
                break

        app_url = self.page.url

        # 1. Extract Client ID
        logger.info("   Extracting Client ID...")
        client_id_node = self.page.wait_for_selector(GitHubSelectors.CLIENT_ID_DISPLAY)
        if not client_id_node:
            raise Exception("Could not find Client ID element")

        client_id = client_id_node.inner_text().strip()
        logger.info(f"   ✅ Client ID: {client_id}")

        # 2. Generate Client Secret
        logger.info("   Generating Client Secret...")
        self._generate_secret()

        # 3. Capture the newly generated secret
        client_secret = self._capture_secret(client_id)

        return OAuthCredentials(
            client_id=client_id,
            client_secret=client_secret,
            app_name=config.name,
            app_url=app_url,
        )

    def _generate_secret(self):
        """Finds and clicks the 'Generate a new client secret' button."""
        # Scroll to bottom to ensure elements are viewport-visible (helps with flaky clicks)
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)  # Give page time to settle after scroll

        clicked = False
        for selector in GitHubSelectors.GENERATE_SECRET_BUTTONS:
            try:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    clicked = True
                    logger.info(f"   Clicked via selector: {selector}")
                    break
            except Exception:
                continue

        if not clicked:
            # Fallback: look for ANY clickable element with 'secret' and 'generate' in the text
            logger.warning("   Standard buttons not found, trying fuzzy match...")
            for tag in ["button", "a", "input", "summary"]:
                for el in self.page.query_selector_all(tag):
                    try:
                        text = (
                            el.inner_text().lower()
                            if tag != "input"
                            else (el.get_attribute("value") or "").lower()
                        )
                        if "secret" in text and "generate" in text:
                            el.click()
                            clicked = True
                            logger.info(f"   Clicked via fuzzy match on <{tag}>")
                            break
                    except Exception:
                        continue
                if clicked:
                    break

        if not clicked:
            # Last resort: submit any form that mentions secret
            forms = self.page.query_selector_all("form")
            for form in forms:
                try:
                    action = form.get_attribute("action") or ""
                    if "secret" in action.lower():
                        submit_btn = form.query_selector(
                            'button[type="submit"], input[type="submit"]'
                        )
                        if submit_btn:
                            submit_btn.click()
                            clicked = True
                            logger.info("   Clicked via form submit fallback")
                            break
                except Exception:
                    continue

        if not clicked:
            raise Exception(
                "Could not find 'Generate client secret' button. Please click it manually!"
            )

        # GitHub may require re-authentication after clicking generate secret
        time.sleep(1)
        self.handle_sudo_mode()

    def _capture_secret(self, client_id: str) -> str:
        """
        Wait for the secret to actally appear on the page and scrape it.
        We exclude the client_id to make sure we don't grab the wrong code block.
        """
        # The secret usually appears in a flash message or a new table row
        # We look for a code block that is NOT the client ID and is long enough

        for _ in range(20):  # Try for 10 seconds (20 * 0.5s)
            codes = self.page.query_selector_all("code")
            for code_el in codes:
                text = code_el.inner_text().strip()
                # Secrets are usually 40 chars hex, Client IDs are ~20 chars
                if len(text) > 30 and text != client_id:
                    logger.info("   ✅ Client Secret captured successfully!")
                    return text
            time.sleep(0.5)

        # Fallback: ask user to paste it
        logger.error("❌ Could not auto-capture the secret.")
        print("\n" + "=" * 60)
        print("Please copy the Client Secret from the browser and paste it here:")
        print("=" * 60 + "\n")
        return input("Client Secret: ").strip()


def print_banner():
    """Print a nice ASCII banner."""
    banner = """
╔═════════════════════════════════════════════════╗
║                                                 ║
║   🔐      GitHub OAuth App Creator              ║
║       Automated OAuth application setup         ║
║                                                 ║
╚═════════════════════════════════════════════════╝
"""
    print("\033[96m" + banner + "\033[0m")


def print_menu():
    """Print the interactive menu."""
    print("\n\033[93m┌─────────────────────────────────────┐\033[0m")
    print(
        "\033[93m│\033[0m  \033[1mWhat would you like to do?\033[0m         \033[93m│\033[0m"
    )
    print("\033[93m├─────────────────────────────────────┤\033[0m")
    print(
        "\033[93m│\033[0m  \033[92m1.\033[0m Create new OAuth app            \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m2.\033[0m Create DEV + PROD apps          \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m3.\033[0m Verify existing credentials     \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m4.\033[0m View saved credentials (.env)   \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m5.\033[0m Delete OAuth app from GitHub    \033[93m│\033[0m"
    )
    print("\033[93m│\033[0m  \033[92m6.\033[0m Clear browser session           \033[93m│\033[0m")
    print("\033[93m│\033[0m  \033[92m7.\033[0m View Secure Audit Log           \033[93m│\033[0m")
    print("\033[93m│\033[0m  \033[91m8.\033[0m Exit                            \033[93m│\033[0m")
    print("\033[93m└─────────────────────────────────────┘\033[0m")


def prompt(text: str, default: str = None, password: bool = False) -> str:
    """Styled input prompt."""
    if default:
        display = f"\033[94m➤\033[0m {text} \033[90m[{default}]\033[0m: "
    else:
        display = f"\033[94m➤\033[0m {text}: "

    if password:
        import getpass

        value = getpass.getpass(display)
    else:
        value = input(display)

    return value.strip() if value.strip() else (default or "")


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Yes/No prompt."""
    hint = "[Y/n]" if default else "[y/N]"
    response = input(f"\033[94m➤\033[0m {text} {hint}: ").strip().lower()

    if not response:
        return default
    return response in ["y", "yes", "true", "1"]


def _normalize_path_input(value: str) -> str:
    """Normalize user-entered path fragments to absolute URL paths."""
    value = value.strip()
    if not value or value == "/":
        return "/"
    return value if value.startswith("/") else f"/{value}"


def _extract_default_path(url: str, fallback: str) -> str:
    """Extract a path from a URL, preserving query/fragment when present."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return fallback

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if parsed.fragment:
        path = f"{path}#{parsed.fragment}"
    return path


def _build_url_from_base_and_path(base_url: str, path: str) -> str:
    """Join a base URL and path while keeping root paths clean."""
    normalized_path = _normalize_path_input(path)
    if normalized_path == "/":
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}{normalized_path}"


def prompt_local_or_custom_urls(
    provider: str, default_homepage: str, default_callback: str
) -> tuple[str, str]:
    """
    Collect homepage/callback URLs.

    Default flow assumes localhost and only asks for paths.
    Users can type `d` to restart URL entry in custom-domain mode.
    """
    parsed_homepage = urlparse(default_homepage)
    if parsed_homepage.hostname in {"localhost", "127.0.0.1"}:
        local_base = f"{parsed_homepage.scheme or 'http'}://{parsed_homepage.netloc}"
    else:
        local_base = "http://localhost:3000"

    local_homepage_path = _extract_default_path(default_homepage, "/")
    local_callback_path = _extract_default_path(
        default_callback, f"/api/auth/callback/{provider}"
    )

    print(
        "\033[94m➤\033[0m URL mode: localhost paths only "
        f"\033[90m[{local_base}]\033[0m"
    )
    print(
        "   Press \033[96md\033[0m during path entry to restart in custom domain mode."
    )

    homepage_path = prompt(
        f"Homepage path (after {local_base})", local_homepage_path
    ).strip()
    if homepage_path.lower() == "d":
        print("\033[93m↺ Restarting URL prompts in custom domain mode...\033[0m")
        homepage_url = prompt("Homepage URL", default_homepage).rstrip("/")
        custom_callback = f"{homepage_url}/api/auth/callback/{provider}"
        callback_url = prompt("Callback URL", custom_callback)
        return homepage_url, callback_url

    callback_path = prompt(
        f"Callback path (after {local_base})", local_callback_path
    ).strip()
    if callback_path.lower() == "d":
        print("\033[93m↺ Restarting URL prompts in custom domain mode...\033[0m")
        homepage_url = prompt("Homepage URL", default_homepage).rstrip("/")
        custom_callback = f"{homepage_url}/api/auth/callback/{provider}"
        callback_url = prompt("Callback URL", custom_callback)
        return homepage_url, callback_url

    homepage_url = _build_url_from_base_and_path(local_base, homepage_path)
    callback_url = _build_url_from_base_and_path(local_base, callback_path)
    return homepage_url, callback_url


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to clipboard. Works on Mac (pbcopy) and Linux (xclip/xsel).
    Returns True on success, False on failure.
    """
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            logger.info("✅ Copied to clipboard (pbcopy)")
            return True
        else:  # Non-macOS systems
            # Try xclip first, then xsel
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(),
                    check=True,
                )
                logger.info("✅ Copied to clipboard (xclip)")
                return True
            except FileNotFoundError:
                try:
                    subprocess.run(
                        ["xsel", "--clipboard", "--input"],
                        input=text.encode(),
                        check=True,
                    )
                    logger.info("✅ Copied to clipboard (xsel)")
                    return True
                except FileNotFoundError:
                    logger.warning("⚠️  No clipboard tool found. Install xclip or xsel.")
                    return False
    except Exception as e:
        logger.warning(f"⚠️  Could not copy to clipboard: {e}")
        return False


def select_env_file() -> str:
    """
    Prompt user to select which .env file to write to.
    Returns the filename as a string.
    """
    print("\n\033[93m┌─────────────────────────────────────┐\033[0m")
    print(
        "\033[93m│\033[0m  \033[1mWhich .env file?\033[0m                  \033[93m│\033[0m"
    )
    print("\033[93m├─────────────────────────────────────┤\033[0m")
    print(
        "\033[93m│\033[0m  \033[92m1.\033[0m .env                           \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m2.\033[0m .env.local                     \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m3.\033[0m .env.production                \033[93m│\033[0m"
    )
    print("\033[93m└─────────────────────────────────────┘\033[0m")

    choice = input("\n\033[94m➤\033[0m Enter choice (1-3): ").strip()

    if choice == "1":
        return ".env"
    elif choice == "2":
        return ".env.local"
    elif choice == "3":
        return ".env.production"
    else:
        print("\033[93m⚠️  Invalid choice, defaulting to .env\033[0m")
        return ".env"


def get_unique_key_prefix(env_path: Path, base_key: str = "GITHUB_CLIENT_ID") -> str:
    """
    Determine the appropriate prefix for a key to avoid overwrites.
    Returns empty string if key doesn't exist.
    Returns 'GENERATED' if base key exists.
    Returns 'GENERATED_2', 'GENERATED_3', etc. for subsequent duplicates.
    """
    if not env_path.exists():
        return ""

    content = env_path.read_text()

    # Check if base key exists (without any prefix)
    # Match exact key at start of line or after newline
    pattern = rf'^{base_key}=|^{base_key}="'
    if not re.search(pattern, content, re.MULTILINE):
        return ""

    # Key exists, find next available prefix
    if not re.search(r"^GENERATED_GITHUB_CLIENT_ID=", content, re.MULTILINE):
        return "GENERATED"

    # Find the next available number
    n = 2
    while re.search(rf"^GENERATED_{n}_GITHUB_CLIENT_ID=", content, re.MULTILINE):
        n += 1
    return f"GENERATED_{n}"


def archive_old_keys(env_path: Path, base_key: str = "GITHUB_CLIENT_ID") -> bool:
    """
    Comment out existing keys with # OLD_ prefix.
    Returns True if changes were made.
    """
    if not env_path.exists():
        return False

    content = env_path.read_text()
    new_content = content

    # Regex to find active keys (not already commented)
    # Replaces 'KEY=VAL' with '# OLD_KEY=VAL'

    patterns = [
        (rf"^{base_key}=", f"# OLD_{base_key}="),
        (
            rf"^{base_key.replace('ID', 'SECRET')}=",
            f"# OLD_{base_key.replace('ID', 'SECRET')}=",
        ),
        # Also handle quoted versions just in case
        (rf'^{base_key}="', f'# OLD_{base_key}="'),
        (
            rf'^{base_key.replace("ID", "SECRET")}="',
            f'# OLD_{base_key.replace("ID", "SECRET")}="',
        ),
    ]

    changes = 0
    for pattern, replacement in patterns:
        new_content, count = re.subn(
            pattern, replacement, new_content, flags=re.MULTILINE
        )
        changes += count

    if changes > 0:
        env_path.write_text(new_content)
        return True
    return False


def write_credentials_to_env(
    creds: "OAuthCredentials",
    env_file: str,
    prefix: str = "",
    force_prefix: bool = False,
) -> bool:
    """
    Write credentials to an .env file.
    If conflict exists:
      1. If force_prefix is True, usage provided prefix (e.g. PROD_)
      2. Otherwise, prompt user: Archive old keys OR use GENERATED_ prefix
    """
    env_path = Path(env_file)

    # Check for conflicts
    conflict = False
    if get_unique_key_prefix(env_path):
        conflict = True

    final_prefix = prefix
    should_archive = False

    # If there is a conflict and we aren't forced to use a specific prefix
    if conflict and not force_prefix and not prefix:
        print(f"\n\033[93m⚠️  Warning: Credentials already exist in {env_file}!\033[0m")
        print("   How do you want to handle this?")
        print(
            "   \033[96m[1]\033[0m Add new keys with \033[1mGENERATED_\033[0m prefix (keep old)"
        )
        print(
            "   \033[96m[2]\033[0m Archive old keys (\033[1m# OLD_...\033[0m) and use standard names"
        )

        choice = input("\n\033[94m➤\033[0m Choice [1]: ").strip()

        if choice == "2":
            should_archive = True
        else:
            final_prefix = get_unique_key_prefix(env_path)

    # Execute archiving if chosen
    if should_archive:
        if archive_old_keys(env_path):
            logger.info(f"   Archived old keys in {env_file}")

    # Determine content to write
    if final_prefix:
        env_content = creds.to_env_string_with_prefix(final_prefix)
        if not force_prefix:  # If it wasn't forced (like PROD_), warn the user
            print(f"    Using prefix: \033[96m{final_prefix}_\033[0m")
    else:
        env_content = creds.to_env_string()

    try:
        # Append to file (create if doesn't exist)
        with open(env_path, "a") as f:
            f.write(env_content)
        logger.info(f"✅ Credentials saved to {env_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to write to {env_file}: {e}")
        return False


def prompt_output_options() -> tuple:
    """
    Prompt user for how they want to handle credentials.
    Returns (copy_clipboard: bool, write_env: bool, env_file: str or None)
    """
    print("\n\033[93m┌─────────────────────────────────────┐\033[0m")
    print(
        "\033[93m│\033[0m  \033[1mHow to save credentials?\033[0m          \033[93m│\033[0m"
    )
    print("\033[93m├─────────────────────────────────────┤\033[0m")
    print(
        "\033[93m│\033[0m  \033[92m1.\033[0m Copy to clipboard              \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m2.\033[0m Write to .env file             \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m3.\033[0m Both (clipboard + .env)        \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m4.\033[0m Just display (no save)         \033[93m│\033[0m"
    )
    print("\033[93m└─────────────────────────────────────┘\033[0m")

    choice = input("\n\033[94m➤\033[0m Enter choice (1-4): ").strip()

    copy_clipboard = False
    write_env = False
    env_file = None

    if choice == "1":
        copy_clipboard = True
    elif choice == "2":
        write_env = True
        env_file = select_env_file()
    elif choice == "3":
        copy_clipboard = True
        write_env = True
        env_file = select_env_file()
    elif choice == "4":
        pass  # Just display
    else:
        print("\033[93m⚠️  Invalid choice, just displaying.\033[0m")

    return (copy_clipboard, write_env, env_file)


def interactive_create():
    """Interactive OAuth app creation flow."""
    print("\n\033[1m📝 Create New OAuth Application\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    # Load .env file if it exists
    from dotenv import load_dotenv

    load_dotenv()

    # Get defaults from environment variables (from setup.sh)
    default_app_name = os.getenv("OAUTH_APP_NAME", "my-oauth-app")
    default_description = os.getenv("OAUTH_APP_DESCRIPTION", "Created via automation")
    default_homepage = os.getenv("OAUTH_BASE_URL", "http://localhost:3000")
    default_password = os.getenv("GITHUB_PASSWORD", "")

    # Gather inputs with .env defaults
    app_name = prompt("Application name", default_app_name)
    homepage_url, callback_url = prompt_local_or_custom_urls(
        "github",
        default_homepage,
        f"{default_homepage.rstrip('/')}/api/auth/callback/github",
    )

    # Only prompt for password if not in env
    if default_password:
        password = default_password
        print(
            f"\033[94m➤\033[0m GitHub password (for sudo mode): \033[90m(loaded from .env)\033[0m"
        )
    else:
        password = prompt("GitHub password (for sudo mode)", password=True)

    # New output options
    copy_clipboard, write_env, env_file = prompt_output_options()
    verify = prompt_yes_no("Verify credentials after creation?", True)

    print("\n\033[90m" + "─" * 40 + "\033[0m")
    print("\033[1m📋 Configuration Summary:\033[0m")
    print(f"   • App Name:     \033[96m{app_name}\033[0m")
    print(f"   • Homepage:     \033[96m{homepage_url}\033[0m")
    print(f"   • Callback:     \033[96m{callback_url}\033[0m")
    print(
        f"   • Password:     \033[96m{'••••••••' if password else '(manual entry)'}\033[0m"
    )
    print(f"   • Clipboard:    \033[96m{'Yes' if copy_clipboard else 'No'}\033[0m")
    print(f"   • Write to:     \033[96m{env_file if write_env else 'None'}\033[0m")
    print(f"   • Verify:       \033[96m{'Yes' if verify else 'No'}\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    if not prompt_yes_no("Proceed with these settings?", True):
        print("\033[93m⚠️  Cancelled.\033[0m")
        return

    # Run the automation
    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GitHubAutomator(page, password=password if password else None)

        if not automator.ensure_logged_in():
            return

        config = OAuthConfig(
            name=app_name, homepage_url=homepage_url, callback_url=callback_url
        )
        creds = automator.create_oauth_app(config)

        print("\n\033[92m" + "─" * 60)
        print(" SUCCESS: Application Created Successfully")
        print("─" * 60 + "\033[0m")
        print(creds.to_env_string())

        # Handle credential output
        if copy_clipboard:
            copy_to_clipboard(creds.to_env_string())

        if write_env and env_file:
            write_credentials_to_env(creds, env_file)

        # Secure Logging
        if HAS_AUDIT_LOGGER and os.getenv("ENABLE_SECURE_LOGGING", "false").lower() == "true":
            try:
                audit = AuditLogger()
                audit.log_credential(
                    app_name=creds.app_name, 
                    client_id=creds.client_id, 
                    client_secret=creds.client_secret, 
                    homepage=homepage_url,
                    env_type="DEV"
                )
            except Exception as e:
                logger.warning(f"Failed to securely log credential: {e}")

        if verify:
            if creds.verify():
                logger.info("🎉 All checks passed!")
            else:
                logger.warning(
                    "⚠️  Verification had some warnings - credentials may still work"
                )

        # Testing mode: Offer to delete the app immediately
        print("\n\033[90m" + "─" * 40 + "\033[0m")
        if prompt_yes_no("TEST MODE: Delete this app now?", False):
            if creds.app_url:
                if automator.delete_oauth_app(creds.app_url, creds.app_name):
                    print(f"\033[92m✅ Deleted {creds.app_name}\033[0m")
            else:
                logger.warning("⚠️  Cannot delete: App URL was not captured")

        time.sleep(2)

    except Exception as e:
        logger.error(f"Automation failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


def prompt_dual_env_options() -> tuple:
    """
    Prompt user for how they want to handle credentials in Dual Mode.
    Returns (copy_clipboard: bool, write_mode: str, dev_file: str, prod_file: str)
    write_mode is 'combined', 'split', or 'none'
    """
    print("\n\033[93m┌─────────────────────────────────────┐\033[0m")
    print(
        "\033[93m│\033[0m  \033[1mHow to save credentials?\033[0m          \033[93m│\033[0m"
    )
    print("\033[93m├─────────────────────────────────────┤\033[0m")
    print(
        "\033[93m│\033[0m  \033[92m1.\033[0m Copy to clipboard only         \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m2.\033[0m Save both to same .env file    \033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m3.\033[0m Split (DEV→.env, PROD→.env.prod)\033[93m│\033[0m"
    )
    print(
        "\033[93m│\033[0m  \033[92m4.\033[0m Just display (no save)         \033[93m│\033[0m"
    )
    print("\033[93m└─────────────────────────────────────┘\033[0m")

    choice = input("\n\033[94m➤\033[0m Enter choice (1-4): ").strip()

    copy_clipboard = choice in ["1", "2", "3"]
    write_mode = "none"
    dev_file = None
    prod_file = None

    if choice == "2":
        write_mode = "combined"
        print("\n\033[1mSelect file for BOTH apps:\033[0m")
        dev_file = select_env_file()
        prod_file = dev_file
    elif choice == "3":
        write_mode = "split"
        print("\n\033[1mSelect file for DEV app:\033[0m")
        print("\033[90m(Usually .env or .env.local)\033[0m")
        dev_file = select_env_file()

        print("\n\033[1mSelect file for PROD app:\033[0m")
        print("\033[90m(Usually .env.production)\033[0m")
        prod_file = select_env_file()

    return (copy_clipboard, write_mode, dev_file, prod_file)


def interactive_create_dual():
    """Interactive OAuth app creation for both DEV and PROD environments."""
    print("\n\033[1m📝 Create DEV + PROD OAuth Applications\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    # Load .env file if it exists
    from dotenv import load_dotenv

    load_dotenv()

    # Get defaults from environment variables
    default_app_name = os.getenv("OAUTH_APP_NAME", "my-oauth-app")
    default_dev_homepage = os.getenv("OAUTH_BASE_URL", "http://localhost:3000")
    default_prod_homepage = os.getenv(
        "OAUTH_PROD_BASE_URL", "https://your-production-domain.com"
    )
    callback_path = "/api/auth/callback/github"
    default_password = os.getenv("GITHUB_PASSWORD", "")

    print("\033[96mℹ️  This will create TWO OAuth apps:\033[0m")
    print("   1. DEV app (for local development)")
    print("   2. PROD app (for production)\n")
    print("\033[96mℹ️  Both apps will use the same callback path:\033[0m")
    print(f"   {callback_path}\n")

    # Gather inputs
    base_app_name = prompt("Base application name", default_app_name)
    dev_homepage = prompt("DEV Homepage URL", default_dev_homepage).rstrip("/")
    prod_homepage = prompt("PROD Homepage URL", default_prod_homepage).rstrip("/")
    custom_callback_path = prompt("Callback path (same for both)", callback_path)

    dev_callback = f"{dev_homepage}{custom_callback_path}"
    prod_callback = f"{prod_homepage}{custom_callback_path}"

    # Only prompt for password if not in env
    if default_password:
        password = default_password
        print(
            f"\033[94m➤\033[0m GitHub password (for sudo mode): \033[90m(loaded from .env)\033[0m"
        )
    else:
        password = prompt("GitHub password (for sudo mode)", password=True)

    # Dual Mode Output Options
    copy_clipboard, write_mode, dev_file, prod_file = prompt_dual_env_options()
    verify = prompt_yes_no("Verify credentials after creation?", True)

    # Build app names
    dev_app_name = f"{base_app_name}-dev"
    prod_app_name = f"{base_app_name}-prod"

    print("\n\033[90m" + "─" * 50 + "\033[0m")
    print("\033[1m📋 Configuration Summary:\033[0m")
    print("\033[90m" + "─" * 50 + "\033[0m")
    print("\033[93m  DEV App:\033[0m")
    print(f"   • Name:         \033[96m{dev_app_name}\033[0m")
    print(f"   • Homepage:     \033[96m{dev_homepage}\033[0m")
    print(f"   • Callback:     \033[96m{dev_callback}\033[0m")
    if write_mode == "split":
        print(f"   • Save to:      \033[96m{dev_file}\033[0m")

    print()
    print("\033[93m  PROD App:\033[0m")
    print(f"   • Name:         \033[96m{prod_app_name}\033[0m")
    print(f"   • Homepage:     \033[96m{prod_homepage}\033[0m")
    print(f"   • Callback:     \033[96m{prod_callback}\033[0m")
    if write_mode == "split":
        print(f"   • Save to:      \033[96m{prod_file}\033[0m")

    print("\033[90m" + "─" * 50 + "\033[0m")
    print(
        f"   • Password:     \033[96m{'••••••••' if password else '(manual entry)'}\033[0m"
    )
    print(f"   • Clipboard:    \033[96m{'Yes' if copy_clipboard else 'No'}\033[0m")

    if write_mode == "combined":
        print(f"   • Write BOTH to:\033[96m{dev_file}\033[0m")
    elif write_mode == "none":
        print(f"   • Write to .env:\033[96mNo\033[0m")

    print(f"   • Verify:       \033[96m{'Yes' if verify else 'No'}\033[0m")
    print("\033[90m" + "─" * 50 + "\033[0m\n")

    if not prompt_yes_no("Proceed with creating BOTH apps?", True):
        print("\033[93m⚠️  Cancelled.\033[0m")
        return

    # Run the automation
    browser_mgr = BrowserManager(headless=False)
    all_creds_text = ""
    created_creds = []

    try:
        page = browser_mgr.start()
        automator = GitHubAutomator(page, password=password if password else None)

        if not automator.ensure_logged_in():
            return

        # Create DEV app
        print("\n\033[93m" + "═" * 50)
        print(" Creating DEV App...")
        print("═" * 50 + "\033[0m\n")

        dev_config = OAuthConfig(
            name=dev_app_name, homepage_url=dev_homepage, callback_url=dev_callback
        )
        dev_creds = automator.create_oauth_app(dev_config)
        created_creds.append(("DEV", dev_creds))

        print("\n\033[92m✅ DEV app created successfully!\033[0m")

        # Create PROD app
        print("\n\033[93m" + "═" * 50)
        print(" Creating PROD App...")
        print("═" * 50 + "\033[0m\n")

        prod_config = OAuthConfig(
            name=prod_app_name, homepage_url=prod_homepage, callback_url=prod_callback
        )
        prod_creds = automator.create_oauth_app(prod_config)
        created_creds.append(("PROD", prod_creds))

        print("\n\033[92m✅ PROD app created successfully!\033[0m")

        # Display results
        print("\n\033[92m" + "═" * 60)
        print(" SUCCESS: Both Applications Created!")
        print("═" * 60 + "\033[0m")

        # Format credentials for DEV
        dev_env_text = f'''
# GitHub OAuth Credentials - DEV ({dev_creds.app_name})
GITHUB_CLIENT_ID="{dev_creds.client_id}"
GITHUB_CLIENT_SECRET="{dev_creds.client_secret}"
'''

        # Format credentials for PROD (with different key names for clarity)
        prod_env_text = f'''
# GitHub OAuth Credentials - PROD ({prod_creds.app_name})
GITHUB_CLIENT_ID_PROD="{prod_creds.client_id}"
GITHUB_CLIENT_SECRET_PROD="{prod_creds.client_secret}"
'''

        all_creds_text = dev_env_text + prod_env_text
        print(all_creds_text)

        # Handle credential output
        if copy_clipboard:
            copy_to_clipboard(all_creds_text)

        if write_mode != "none" and dev_file:
            # Write DEV credentials (always standard keys)
            write_credentials_to_env(dev_creds, dev_file)

            if write_mode == "combined":
                # Combined: PROD credentials MUST be prefixed with PROD_ in the same file
                # pass force_prefix=True to bypass interactive duplicate check prompt for this specific prefix
                write_credentials_to_env(
                    prod_creds, dev_file, prefix="PROD", force_prefix=True
                )

            elif write_mode == "split" and prod_file:
                # Split: Write PROD with standard keys to separate file
                # No forced prefix - allow standard duplicate handling (archive vs generated)
                write_credentials_to_env(prod_creds, prod_file)
        
        # Secure Logging
        if HAS_AUDIT_LOGGER and os.getenv("ENABLE_SECURE_LOGGING", "false").lower() == "true":
            try:
                audit = AuditLogger()
                # Log DEV
                audit.log_credential(
                    app_name=dev_creds.app_name, 
                    client_id=dev_creds.client_id, 
                    client_secret=dev_creds.client_secret, 
                    homepage=dev_homepage,
                    env_type="DEV"
                )
                # Log PROD
                audit.log_credential(
                    app_name=prod_creds.app_name, 
                    client_id=prod_creds.client_id, 
                    client_secret=prod_creds.client_secret, 
                    homepage=prod_homepage,
                    env_type="PROD"
                )
            except Exception as e:
                logger.warning(f"Failed to securely log credentials: {e}")

        if verify:
            print("\n\033[1m🔍 Verifying credentials...\033[0m")
            for env_name, creds in created_creds:
                print(f"\n  Verifying {env_name}:")
                if creds.verify():
                    print(f"  \033[92m✅ {env_name} credentials valid!\033[0m")
                else:
                    print(f"  \033[93m⚠️  {env_name} verification had warnings\033[0m")

        # Testing mode: Offer to delete the apps immediately
        print("\n\033[90m" + "─" * 40 + "\033[0m")
        if prompt_yes_no("TEST MODE: Delete BOTH apps now?", False):
            for env_name, creds in created_creds:
                if creds.app_url:
                    if automator.delete_oauth_app(creds.app_url, creds.app_name):
                        print(
                            f"\033[92m✅ Deleted {creds.app_name} ({env_name})\033[0m"
                        )
                else:
                    logger.warning(
                        f"⚠️  Cannot delete {env_name}: App URL was not captured"
                    )

        time.sleep(2)

    except Exception as e:
        logger.error(f"Automation failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


def interactive_verify():
    """Verify existing credentials."""
    print("\n\033[1m🔍 Verify Existing Credentials\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    client_id = prompt("Client ID")
    client_secret = prompt("Client Secret", password=True)

    if not client_id or not client_secret:
        print("\033[91m❌ Both Client ID and Secret are required.\033[0m")
        return

    creds = OAuthCredentials(
        client_id=client_id, client_secret=client_secret, app_name="manual-verify"
    )

    if creds.verify():
        print("\n\033[92m✅ Credentials appear valid!\033[0m")
    else:
        print("\n\033[91m❌ Verification failed.\033[0m")


def view_saved_credentials():
    """View credentials from .env file."""
    print("\n\033[1m📄 Saved Credentials\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    env_path = Path(".env")
    if not env_path.exists():
        print("\033[93m⚠️  No .env file found.\033[0m")
        return

    content = env_path.read_text()

    # Find GitHub OAuth sections
    import re

    matches = re.findall(
        r'# GitHub OAuth Credentials.*?\nGITHUB_CLIENT_ID="([^"]+)"\nGITHUB_CLIENT_SECRET="([^"]+)"',
        content,
    )

    if not matches:
        print("\033[93m⚠️  No GitHub OAuth credentials found in .env\033[0m")
        return

    for i, (client_id, client_secret) in enumerate(matches, 1):
        print(f"\033[96m[{i}]\033[0m Client ID:     {client_id}")
        print(f"    Client Secret: {client_secret[:10]}...{client_secret[-4:]}")
        print()

    # Offer to test connection
    if prompt_yes_no("\nTest a saved credential?", False):
        try:
            choice = int(
                input("\033[94m➤\033[0m Enter credential number to test: ").strip()
            )
            if 1 <= choice <= len(matches):
                client_id, client_secret = matches[choice - 1]

                print(f"\n\033[1m🔍 Testing credential [{choice}]...\033[0m")
                creds = OAuthCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                    app_name=f"saved-credential-{choice}",
                )

                if creds.verify():
                    print("\n\033[92m✅ Credential is valid!\033[0m")
                else:
                    print("\n\033[91m❌ Verification failed.\033[0m")
            else:
                print("\033[91m❌ Invalid selection.\033[0m")
        except (ValueError, KeyboardInterrupt):
            print("\n\033[93m⚠️  Cancelled.\033[0m")


def interactive_view_audit_log():
    """Decrypt and display the secure audit log."""
    print("\n\033[1m🔐 Secure Audit Log\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")
    
    if not HAS_AUDIT_LOGGER or not os.path.exists(os.path.expanduser("~/.oauth-automator/.key")):
        print("\033[93m⚠️  No secure log or key found.\033[0m")
        print("   Secure logging might not be enabled or no apps created yet.")
        
        if prompt_yes_no("\nEnable secure audit logging now?"):
            # Update .env
            env_path = Path(".env")
            if env_path.exists():
                content = env_path.read_text()
                if "ENABLE_SECURE_LOGGING=" in content:
                    content = re.sub(r"ENABLE_SECURE_LOGGING=.*", "ENABLE_SECURE_LOGGING=true", content)
                else:
                    content += "\nENABLE_SECURE_LOGGING=true"
                env_path.write_text(content)
                logger.info("✅ Updated .env configuration.")
            
            # Initialize Logger (creates keys)
            try:
                # Force environment var for this session
                os.environ["ENABLE_SECURE_LOGGING"] = "true"
                audit = AuditLogger()
                print("\033[92m✅ Secure logging enabled & keys generated.\033[0m")
                print("   Future apps will be logged.")
            except Exception as e:
                print(f"\033[91m❌ Failed to initialize logger: {e}\033[0m")
        return

    try:
        audit = AuditLogger()
        entries = audit.read_log()
        
        if not entries:
            print("   \033[90m(Log is empty)\033[0m")
            return
            
        print(f"\033[96mFound {len(entries)} entries:\033[0m\n")
        
        # Sort by timestamp desc
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        for i, entry in enumerate(entries, 1):
            ts = entry.get('timestamp', 'Unknown').replace('T', ' ')[:19]
            env = entry.get('env_type', 'UNK')
            name = entry.get('app_name', 'Unknown')
            cid = entry.get('client_id', '???')
            
            print(f"\033[94m[{i}] {ts} \033[0m| \033[1m{env}\033[0m | {name}")
            print(f"      Client ID: {cid}")
        
        print()
        if prompt_yes_no("Reveal full secrets for an entry?", False):
            try:
                choice = int(input("\033[94m➤\033[0m Enter entry number: ").strip())
                if 1 <= choice <= len(entries):
                    item = entries[choice-1]
                    print(f"\n\033[1m🔓 Secrets for {item['app_name']}:\033[0m")
                    print(f"   Client ID:     {item['client_id']}")
                    print(f"   Client Secret: {item['client_secret']}")
                    input("\nPress Enter to clear screen...")
                    print("\033[2J\033[H", end="")  # Clear screen
                else:
                    print("\033[91m❌ Invalid selection.\033[0m")
            except ValueError:
                print("\033[91m❌ Invalid input.\033[0m")
                
    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")


def interactive_delete():
    """Interactive OAuth app deletion with bulk support."""
    print("\n\033[1m🗑️  Delete OAuth App from GitHub\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    password = prompt("GitHub password (for authentication)", password=True)

    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GitHubAutomator(page, password=password if password else None)

        if not automator.ensure_logged_in():
            return

        # List OAuth apps
        apps = automator.list_oauth_apps()

        if not apps:
            print("\033[93m⚠️  No OAuth apps found.\033[0m")
            return

        print("\n\033[1mYour OAuth Apps:\033[0m\n")
        for i, app in enumerate(apps, 1):
            print(f"\033[96m[{i}]\033[0m {app['name']}")

        print()
        print(
            "\033[90mTip: You can enter multiple numbers separated by commas (e.g. '1, 3, 5')\033[0m"
        )

        try:
            choice_str = input(
                "\033[94m➤\033[0m Enter app number(s) to delete (0 to cancel): "
            ).strip()

            if not choice_str or choice_str == "0":
                print("\033[93m⚠️  Cancelled.\033[0m")
                return

            # Parse selections (handle commands and ranges if needed, but simple lists for now)
            # e.g. "1, 3, 5" -> [1, 3, 5]
            try:
                choices = [
                    int(c.strip()) for c in choice_str.split(",") if c.strip().isdigit()
                ]
            except ValueError:
                print("\033[91m❌ Invalid input format.\033[0m")
                return

            if not choices:
                print("\033[93m⚠️  No valid selections.\033[0m")
                return

            # Retrieve selected apps
            selected_apps = []
            for choice in choices:
                if 1 <= choice <= len(apps):
                    selected_apps.append(apps[choice - 1])
                else:
                    print(f"\033[91m⚠️  Skipping invalid number: {choice}\033[0m")

            if not selected_apps:
                return

            print(
                f"\n\033[91m⚠️  Warning: You're about to delete {len(selected_apps)} app(s):\033[0m"
            )
            for app in selected_apps:
                print(f"   - {app['name']}")

            if prompt_yes_no("Are you sure? This cannot be undone.", False):
                success_count = 0
                for app in selected_apps:
                    print(f"\nProcessing: {app['name']}...")
                    if automator.delete_oauth_app(app["url"], app["name"]):
                        print(f"\033[92m✅ Deleted {app['name']}\033[0m")
                        success_count += 1
                    else:
                        print(f"\033[91m❌ Failed to delete {app['name']}\033[0m")

                print(
                    f"\n\033[92mDone! Deleted {success_count}/{len(selected_apps)} apps.\033[0m"
                )
            else:
                print("\033[93m⚠️  Cancelled.\033[0m")

        except (ValueError, KeyboardInterrupt):
            print("\n\033[93m⚠️  Cancelled.\033[0m")

        time.sleep(2)

    except Exception as e:
        logger.error(f"Failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


def clear_session():
    """Clear the saved browser session."""
    print("\n\033[1m🗑️  Clear Browser Session\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    session_dir = Path("./auth_session")
    if not session_dir.exists():
        print("\033[93m⚠️  No session directory found.\033[0m")
        return

    if prompt_yes_no("This will log you out. Continue?", False):
        shutil.rmtree(session_dir)
        print("\033[92m✅ Session cleared. You'll need to log in again.\033[0m")
    else:
        print("\033[93m⚠️  Cancelled.\033[0m")


def interactive_main():
    """Main interactive menu loop."""
    print_banner()

    while True:
        print_menu()
        choice = input("\n\033[94m➤\033[0m Enter choice (1-8): ").strip()

        if choice == "1":
            interactive_create()
        elif choice == "2":
            interactive_create_dual()
        elif choice == "3":
            interactive_verify()
        elif choice == "4":
            view_saved_credentials()
        elif choice == "5":
            interactive_delete()
        elif choice == "6":
            clear_session()
        elif choice == "7":
            interactive_view_audit_log()
        elif choice == "8":
            print("\n\033[96m👋 Goodbye!\033[0m\n")
            break
        else:
            print("\033[91m❌ Invalid choice. Please enter 1-8.\033[0m")


def main():
    """Entry point - supports both CLI and interactive modes."""
    # If no arguments provided, run interactive mode
    if len(sys.argv) == 1:
        interactive_main()
        return

    # Otherwise, use CLI mode
    parser = argparse.ArgumentParser(
        description="GitHub OAuth Automator",
        epilog="Run without arguments for interactive mode.",
    )
    parser.add_argument(
        "--app-name", required=True, help="Name of the OAuth application"
    )
    parser.add_argument(
        "--password", "-p", help="GitHub password for sudo mode authentication"
    )
    parser.add_argument(
        "--write-env", action="store_true", help="Append credentials to .env file"
    )
    parser.add_argument(
        "--verify", "-v", action="store_true", help="Verify credentials after creation"
    )
    parser.add_argument(
        "--homepage-url", default="http://localhost:3000", help="Homepage URL"
    )
    parser.add_argument(
        "--callback-url",
        help="Callback URL (defaults to homepage + /api/auth/callback/github)",
    )

    args = parser.parse_args()

    callback_url = args.callback_url or f"{args.homepage_url}/api/auth/callback/github"

    # Initialize Browser
    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GitHubAutomator(page, password=args.password)

        if not automator.ensure_logged_in():
            return

        config = OAuthConfig(
            name=args.app_name,
            homepage_url=args.homepage_url,
            callback_url=callback_url,
        )
        creds = automator.create_oauth_app(config)

        print("\n" + "🎉" * 20)
        print("SUCCESS! Application Created.")
        print(creds.to_env_string())

        if args.write_env:
            with open(".env", "a") as f:
                f.write(creds.to_env_string())
            logger.info("✅ Saved to .env file")

        if args.verify:
            if creds.verify():
                logger.info("🎉 All checks passed!")
            else:
                logger.warning(
                    "⚠️  Verification had some warnings - credentials may still work"
                )

        time.sleep(3)

    except Exception as e:
        logger.error(f"Automation failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


if __name__ == "__main__":
    main()
