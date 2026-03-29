#!/usr/bin/env python3
"""
Google OAuth App Creator - Production Grade Automation
========================================================
Author: Remco Stoeten
Date: 2025-01-07

This script automates the creation of Google OAuth 2.0 client credentials
through the Google Cloud Console UI using Playwright.

Key Features:
- Persistent Authentication: Reuses your browser session
- Robust Selectors: Handles Google Cloud Console UI variations
- Project Selection: Handles project selection/creation
- Browser Reuse: Optionally connects to your installed Brave/Chrome browser
- Clean Architecture: Separates browser management from automation logic

Usage:
    python google_oauth_automator.py --app-name "MyCoolApp" --write-env
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
from typing import Optional, List, Dict

from playwright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    Playwright,
)
import platform
import subprocess
import re

from github_oauth_automator import (
    BrowserManager,
    copy_to_clipboard,
    prompt,
    prompt_choice,
    prompt_local_or_custom_urls,
    prompt_yes_no,
    select_env_file,
)


# Configure logging
class LogFormatter(logging.Formatter):
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


logger = logging.getLogger("google_auth_automator")
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(LogFormatter())
logger.addHandler(ch)


@dataclass
class GoogleSelectors:
    """Centralized configuration for all DOM selectors in Google Cloud Console."""

    BASE_URL = "https://console.cloud.google.com"

    # Login & Auth
    EMAIL_INPUT = "input[type='email']"
    NEXT_BUTTON = "#identifierNext, button:has-text('Next')"
    PASSWORD_INPUT = "input[type='password']"
    PASSWORD_NEXT = "#passwordNext"

    # Project Selection
    PROJECT_SEARCH_INPUT = "input[placeholder='Search for project']"
    PROJECT_ITEM = "cds-select-item"
    SELECT_PROJECT_BUTTON = "button:has-text('Select')"

    # Navigation
    API_MENU = "[ng-if*='api']"
    CREDENTIALS_MENU = "[href*='credentials']"
    CREATE_CREDENTIALS_BUTTON = "button:has-text('Create Credentials')"
    OAUTH_CLIENT_ID_OPTION = "button:has-text('OAuth client ID')"

    # OAuth Client Creation
    APP_TYPE_WEB = "input[value='WEB']"
    APP_TYPE_DESKTOP = "input[value='DESKTOP']"
    NAME_INPUT = "input[aria-label='Name']"
    AUTHORIZED_JAVASCRIPT_ORIGINS = (
        "div[role='combobox']:has-text('Authorized JavaScript origins')"
    )
    AUTHORIZED_REDIRECT_URIS = (
        "div[role='combobox']:has-text('Authorized redirect URIs')"
    )
    ORIGIN_INPUT = "input[placeholder='https://example.com']"
    REDIRECT_URI_INPUT = "input[placeholder='https://example.com/oauth2callback']"
    CREATE_BUTTON = "button:has-text('Create'), button:has-text('Save')"

    # Credentials Display
    CLIENT_ID_DISPLAY = (
        "cds-copy-to-clipboard[data-id='client-id'], div:has-text('Client ID') code"
    )
    CLIENT_SECRET_DISPLAY = "cds-copy-to-clipboard[data-id='client-secret'], div:has-text('Client secret') code"
    CLOSE_DIALOG_BUTTON = "button:has-text('Close'), button[aria-label='Close']"

    # Consent Screen
    CONSENT_SCREEN_LINK = "a:has-text('OAuth consent screen')"
    CONSENT_EXTERNAL_RADIO = "input[value='EXTERNAL']"
    CONSENT_NAME_INPUT = "input[aria-label='App name']"
    CONSENT_EMAIL_INPUT = "input[aria-label='User support email']"
    SAVE_AND_CONTINUE_BUTTON = (
        "button:has-text('Save and Continue'), button:has-text('Save')"
    )


@dataclass
class GoogleOAuthConfig:
    """Type-safe configuration for the Google OAuth application."""

    name: str
    app_type: str = "web"  # web or desktop
    javascript_origins: List[str] = None
    redirect_uris: List[str] = None
    project_id: Optional[str] = None

    def __post_init__(self):
        if self.javascript_origins is None:
            self.javascript_origins = []
        if self.redirect_uris is None:
            self.redirect_uris = []


@dataclass
class GoogleOAuthCredentials:
    """The output credentials we want to capture."""

    client_id: str
    client_secret: str
    app_name: str
    app_type: str
    project_id: str

    def to_env_string(self) -> str:
        """Returns the credentials formatted for a .env file."""
        return f'''
# Google OAuth Credentials ({self.app_name})
GOOGLE_CLIENT_ID="{self.client_id}"
GOOGLE_CLIENT_SECRET="{self.client_secret}"
GOOGLE_PROJECT_ID="{self.project_id}"
'''

    def to_env_string_with_prefix(self, prefix: str = "") -> str:
        """Returns credentials formatted for .env file with optional prefix."""
        key_prefix = f"{prefix}_" if prefix else ""
        return f'''
# Google OAuth Credentials ({self.app_name})
{key_prefix}GOOGLE_CLIENT_ID="{self.client_id}"
{key_prefix}GOOGLE_CLIENT_SECRET="{self.client_secret}"
{key_prefix}GOOGLE_PROJECT_ID="{self.project_id}"
'''


class GoogleAutomator:
    """
    Encapsulates the business logic for Google Cloud Console interaction.
    Functions here correspond to specific high-level tasks on the website.
    """

    def __init__(self, page: Page):
        self.page = page

    def ensure_logged_in(self) -> bool:
        """
        Verifies login status and waits for user input if needed.
        Returns True if logged in, False if timed out.
        """
        self.page.goto(f"{GoogleSelectors.BASE_URL}/")

        time.sleep(2)

        if self.page.url.startswith("https://accounts.google.com/"):
            logger.info(
                "🔐 Authentication required. Please log in via the browser window."
            )

            try:
                # Wait for navigation away from login page
                self.page.wait_for_url(
                    f"**{GoogleSelectors.BASE_URL}/**", timeout=300_000
                )
                logger.info("✅ Login detected!")
                return True
            except Exception:
                logger.error("❌ Login timed out.")
                return False

        logger.info("✅ Already logged in (session restored)")
        return True

    def select_or_create_project(self, project_id: Optional[str] = None) -> str:
        """
        Select an existing project or create a new one.
        Returns the project ID.
        """
        logger.info(f"📁 Selecting project...")

        # Navigate to project selector
        self.page.goto(f"{GoogleSelectors.BASE_URL}/home/dashboard")

        time.sleep(2)

        # Check if project selector is visible
        project_selector = self.page.query_selector(
            "[role='button']:has-text('Select a project')"
        )

        if project_selector:
            project_selector.click()
            time.sleep(1)

            if project_id:
                logger.info(f"   Searching for project: {project_id}")

                search_input = self.page.query_selector(
                    GoogleSelectors.PROJECT_SEARCH_INPUT
                )
                if search_input:
                    search_input.fill(project_id)
                    time.sleep(1)

                    # Try to find and click the project
                    project_items = self.page.query_selector_all(
                        GoogleSelectors.PROJECT_ITEM
                    )
                    for item in project_items:
                        text = item.inner_text()
                        if project_id.lower() in text.lower():
                            item.click()
                            logger.info(f"   ✅ Selected project: {project_id}")
                            time.sleep(2)
                            return project_id

            # If no project found or specified, prompt user to select
            logger.info("   Please select a project in the browser...")
            time.sleep(3)
            return self._get_current_project_id()

        # No selector visible, already on a project
        return self._get_current_project_id()

    def _get_current_project_id(self) -> str:
        """Extract the current project ID from the page."""
        time.sleep(1)
        # Try to get project ID from URL or page elements
        project_id_match = re.search(r"/project/([^/?]+)", self.page.url)
        if project_id_match:
            return project_id_match.group(1)

        # Fallback: look for project ID in the UI
        project_indicator = self.page.query_selector(
            "[data-project-id], [data-id*='project']"
        )
        if project_indicator:
            return project_indicator.get_attribute("data-project-id") or "unknown"

        logger.warning("   ⚠️  Could not determine project ID")
        return "unknown"

    def setup_consent_screen(self, app_name: str):
        """
        Set up the OAuth consent screen if not already configured.
        """
        logger.info("📝 Setting up OAuth consent screen...")

        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials/consent")

        time.sleep(2)

        # Check if consent screen is already configured
        if "edit" in self.page.url.lower():
            logger.info("   ✅ Consent screen already configured")
            return

        # External user type
        external_radio = self.page.query_selector(
            GoogleSelectors.CONSENT_EXTERNAL_RADIO
        )
        if external_radio:
            external_radio.click()
            time.sleep(0.5)

        # Fill in app name
        name_input = self.page.query_selector(GoogleSelectors.CONSENT_NAME_INPUT)
        if name_input:
            name_input.fill(app_name)
            time.sleep(0.5)

        # Fill in user support email (use email from account or default)
        email_input = self.page.query_selector(GoogleSelectors.CONSENT_EMAIL_INPUT)
        if email_input:
            email_input.fill("noreply@example.com")
            time.sleep(0.5)

        # Click save
        save_button = self.page.query_selector(GoogleSelectors.SAVE_AND_CONTINUE_BUTTON)
        if save_button:
            save_button.click()
            logger.info("   ✅ Consent screen configured")
            time.sleep(2)

    def create_oauth_client(self, config: GoogleOAuthConfig) -> GoogleOAuthCredentials:
        """
        Create a new OAuth 2.0 client ID.
        """
        project_id = self.select_or_create_project(config.project_id)

        logger.info(f"📝 Creating OAuth client: {config.name}")

        # Navigate to credentials page
        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials")

        time.sleep(2)

        # Setup consent screen first if needed
        self.setup_consent_screen(config.name)

        # Navigate back to credentials
        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials")

        time.sleep(2)

        # Click "Create Credentials"
        create_btn = self.page.query_selector(GoogleSelectors.CREATE_CREDENTIALS_BUTTON)
        if not create_btn:
            raise Exception("Could not find 'Create Credentials' button")

        create_btn.click()
        time.sleep(1)

        # Click "OAuth client ID"
        oauth_option = self.page.query_selector(GoogleSelectors.OAUTH_CLIENT_ID_OPTION)
        if not oauth_option:
            raise Exception("Could not find 'OAuth client ID' option")

        oauth_option.click()
        time.sleep(2)

        # Select application type
        if config.app_type.lower() == "web":
            web_radio = self.page.query_selector(GoogleSelectors.APP_TYPE_WEB)
            if web_radio:
                web_radio.click()
        elif config.app_type.lower() == "desktop":
            desktop_radio = self.page.query_selector(GoogleSelectors.APP_TYPE_DESKTOP)
            if desktop_radio:
                desktop_radio.click()

        time.sleep(0.5)

        # Fill in name
        name_input = self.page.query_selector(GoogleSelectors.NAME_INPUT)
        if not name_input:
            raise Exception("Could not find name input field")

        name_input.fill(config.name)
        time.sleep(0.5)

        # Add JavaScript origins (for web apps)
        if config.app_type.lower() == "web" and config.javascript_origins:
            for origin in config.javascript_origins:
                origins_container = self.page.query_selector(
                    GoogleSelectors.AUTHORIZED_JAVASCRIPT_ORIGINS
                )
                if origins_container:
                    origins_container.click()
                    time.sleep(0.5)

                    origin_input = self.page.query_selector(
                        GoogleSelectors.ORIGIN_INPUT
                    )
                    if origin_input:
                        origin_input.fill(origin)
                        time.sleep(0.5)

                        # Press Enter to add
                        origin_input.press("Enter")
                        time.sleep(0.5)

        # Add redirect URIs
        if config.redirect_uris:
            for uri in config.redirect_uris:
                redirect_container = self.page.query_selector(
                    GoogleSelectors.AUTHORIZED_REDIRECT_URIS
                )
                if redirect_container:
                    redirect_container.click()
                    time.sleep(0.5)

                    redirect_input = self.page.query_selector(
                        GoogleSelectors.REDIRECT_URI_INPUT
                    )
                    if redirect_input:
                        redirect_input.fill(uri)
                        time.sleep(0.5)

                        # Press Enter to add
                        redirect_input.press("Enter")
                        time.sleep(0.5)

        # Create the client
        create_button = self.page.query_selector(GoogleSelectors.CREATE_BUTTON)
        if not create_button:
            raise Exception("Could not find Create button")

        create_button.click()
        logger.info("   Submitting OAuth client creation...")
        time.sleep(3)

        # Extract credentials from the dialog
        client_id = self._extract_client_id()
        client_secret = self._extract_client_secret()

        # Close the dialog
        close_button = self.page.query_selector(GoogleSelectors.CLOSE_DIALOG_BUTTON)
        if close_button:
            close_button.click()
            time.sleep(1)

        return GoogleOAuthCredentials(
            client_id=client_id,
            client_secret=client_secret,
            app_name=config.name,
            app_type=config.app_type,
            project_id=project_id,
        )

    def _extract_client_id(self) -> str:
        """Extract client ID from the credentials dialog."""
        for _ in range(10):
            try:
                client_id_el = self.page.query_selector(
                    GoogleSelectors.CLIENT_ID_DISPLAY
                )
                if client_id_el:
                    return client_id_el.inner_text().strip()
            except Exception as e:
                logger.debug(f"DEBUG: Client ID extraction failed: {e}")
                pass
            time.sleep(0.5)

        # Fallback: look for code elements containing client ID pattern
        codes = self.page.query_selector_all("code")
        for code in codes:
            text = code.inner_text().strip()
            # Client IDs are typically .apps.googleusercontent.com format
            if ".apps.googleusercontent.com" in text:
                return text

        raise Exception("Could not extract Client ID from the page")

    def _extract_client_secret(self) -> str:
        """Extract client secret from the credentials dialog."""
        for _ in range(10):
            try:
                client_secret_el = self.page.query_selector(
                    GoogleSelectors.CLIENT_SECRET_DISPLAY
                )
                if client_secret_el:
                    return client_secret_el.inner_text().strip()
            except Exception as e:
                logger.debug(f"DEBUG: Client Secret extraction failed: {e}")
                pass
            time.sleep(0.5)

        raise Exception("Could not extract Client Secret from the page")


def print_banner():
    """Print a nice ASCII banner."""
    banner = """
 ╔═════════════════════════════════════════════════╗
 ║                                                 ║
 ║   🔐      Google OAuth App Creator              ║
 ║       Automated OAuth application setup         ║
 ║                                                 ║
 ╚═════════════════════════════════════════════════╝
 """
    print("\033[96m" + banner + "\033[0m")


def interactive_create():
    """Interactive OAuth app creation flow."""
    print("\n\033[1m📝 Create New Google OAuth Application\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    from dotenv import load_dotenv

    load_dotenv()

    default_app_name = os.getenv("GOOGLE_OAUTH_APP_NAME", "my-google-app")
    default_homepage = os.getenv("OAUTH_BASE_URL", "http://localhost:3000")
    app_name = prompt("Application name", default_app_name)
    app_type = prompt_choice("Application type", ["web", "desktop"], "web").lower()
    homepage_url, callback_url = prompt_local_or_custom_urls(
        "google",
        default_homepage,
        f"{default_homepage.rstrip('/')}/api/auth/callback/google",
    )

    javascript_origins = []
    redirect_uris = []

    if app_type == "web":
        javascript_origins.append(homepage_url)

    redirect_uris.append(callback_url)

    # Output options
    copy_clipboard, write_env, env_file = prompt_output_options()

    print("\n\033[90m" + "─" * 40 + "\033[0m")
    print("\033[1m📋 Configuration Summary:\033[0m")
    print(f"   • App Name:         \033[96m{app_name}\033[0m")
    print(f"   • Type:             \033[96m{app_type}\033[0m")
    print(f"   • Homepage:         \033[96m{homepage_url}\033[0m")
    print(f"   • Callback:         \033[96m{callback_url}\033[0m")
    print(f"   • Clipboard:        \033[96m{'Yes' if copy_clipboard else 'No'}\033[0m")
    print(f"   • Write to:         \033[96m{env_file if write_env else 'None'}\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    if not prompt_yes_no("Proceed with these settings?", True):
        print("\033[93m⚠️  Cancelled.\033[0m")
        return

    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GoogleAutomator(page)

        if not automator.ensure_logged_in():
            return

        config = GoogleOAuthConfig(
            name=app_name,
            app_type=app_type,
            javascript_origins=javascript_origins,
            redirect_uris=redirect_uris,
        )
        creds = automator.create_oauth_client(config)

        print("\n\033[92m" + "─" * 60)
        print(" SUCCESS: Application Created Successfully")
        print("─" * 60 + "\033[0m")
        print(creds.to_env_string())

        if copy_clipboard:
            copy_to_clipboard(creds.to_env_string())

        if write_env and env_file:
            write_google_credentials_to_env(creds, env_file)

        time.sleep(2)

    except Exception as e:
        logger.error(f"Automation failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


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

    choice = prompt_choice("Enter choice (1-4)", ["1", "2", "3", "4"], "4")

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
        pass

    return (copy_clipboard, write_env, env_file)


def write_google_credentials_to_env(
    creds: "GoogleOAuthCredentials",
    env_file: str,
    prefix: str = "",
) -> bool:
    """
    Write Google OAuth credentials to an .env file.
    Simplified version for Google credentials.
    """
    env_path = Path(env_file)

    # Determine content to write
    if prefix:
        env_content = creds.to_env_string_with_prefix(prefix)
    else:
        env_content = creds.to_env_string()

    try:
        with open(env_path, "a") as f:
            f.write(env_content)
        logger.info(f"✅ Credentials saved to {env_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to write to {env_file}: {e}")
        return False


def main():
    """Entry point - supports both CLI and interactive modes."""
    if len(sys.argv) == 1:
        print_banner()
        interactive_create()
        return

    parser = argparse.ArgumentParser(
        description="Google OAuth Automator",
        epilog="Run without arguments for interactive mode.",
    )
    parser.add_argument(
        "--app-name", required=True, help="Name of the OAuth application"
    )
    parser.add_argument(
        "--app-type", default="web", choices=["web", "desktop"], help="Application type"
    )
    parser.add_argument(
        "--homepage-url", default="http://localhost:3000", help="Homepage URL"
    )
    parser.add_argument(
        "--callback-url",
        help="Callback URL (defaults to homepage + /api/auth/callback/google)",
    )
    parser.add_argument(
        "--write-env", action="store_true", help="Append credentials to .env file"
    )
    parser.add_argument("--project-id", help="Google Cloud project ID (optional)")

    args = parser.parse_args()

    callback_url = args.callback_url or f"{args.homepage_url}/api/auth/callback/google"

    javascript_origins = []
    redirect_uris = []

    if args.app_type == "web":
        javascript_origins.append(args.homepage_url)

    redirect_uris.append(callback_url)

    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GoogleAutomator(page)

        if not automator.ensure_logged_in():
            return

        config = GoogleOAuthConfig(
            name=args.app_name,
            app_type=args.app_type,
            javascript_origins=javascript_origins,
            redirect_uris=redirect_uris,
            project_id=args.project_id,
        )
        creds = automator.create_oauth_client(config)

        print("\n" + "🎉" * 20)
        print("SUCCESS! Application Created.")
        print(creds.to_env_string())

        if args.write_env:
            write_google_credentials_to_env(creds, ".env")

        time.sleep(3)

    except Exception as e:
        logger.error(f"Automation failed: {e}")
        input("Press Enter to close browser...")

    finally:
        browser_mgr.close()


if __name__ == "__main__":
    main()
