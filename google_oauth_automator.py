#!/usr/bin/env python3
"""
Google OAuth App Creator - Production Grade Automation
========================================================
Author: Remco Stoeten
Date: 2025-01-07 (Enhanced: 2026-01-10)

This script automates the creation of Google OAuth 2.0 client credentials
through the Google Cloud Console UI using Playwright.

Key Features:
- Persistent Authentication: Reuses your browser session
- Robust Selectors: Handles Google Cloud Console UI variations
- Full Consent Screen Configuration: All OAuth consent screen fields
- Project Selection: Handles project selection/creation
- Browser Reuse: Optionally connects to your installed Brave/Chrome browser
- Clean Architecture: Separates browser management from automation logic
- List & Delete: Manage existing OAuth clients
- Credential Verification: Verify created credentials

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
from dataclasses import dataclass, field
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
    prompt_yes_no,
    select_env_file,
)

from version_check import print_update_notice, check_and_update


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
    BASE_URL = "https://console.cloud.google.com"

    EMAIL_INPUT = "input[type='email']"
    NEXT_BUTTON = "#identifierNext, button:has-text('Next')"
    PASSWORD_INPUT = "input[type='password']"
    PASSWORD_NEXT = "#passwordNext"

    PROJECT_SEARCH_INPUT = "input[placeholder='Search for project'], input[placeholder='Search projects']"
    PROJECT_ITEM = "cds-select-item, [role='option']"
    SELECT_PROJECT_BUTTON = "button:has-text('Select'), button:has-text('Open')"
    PROJECT_SELECTOR_BUTTON = "[aria-label='Select a project'], button:has-text('Select a project'), .cfc-project-selector"

    API_MENU = "[ng-if*='api']"
    CREDENTIALS_MENU = "[href*='credentials']"
    CREATE_CREDENTIALS_BUTTON = "button:has-text('Create Credentials'), button:has-text('Create credentials')"
    OAUTH_CLIENT_ID_OPTION = "button:has-text('OAuth client ID'), [role='menuitem']:has-text('OAuth client ID')"

    APP_TYPE_DROPDOWN = "[aria-label='Application type'], mat-select, cfc-select"
    APP_TYPE_WEB = "[value='WEB'], mat-option:has-text('Web application'), [role='option']:has-text('Web application')"
    APP_TYPE_DESKTOP = "[value='DESKTOP'], mat-option:has-text('Desktop app'), [role='option']:has-text('Desktop app')"
    APP_TYPE_ANDROID = "[value='ANDROID'], mat-option:has-text('Android'), [role='option']:has-text('Android')"
    APP_TYPE_IOS = "[value='IOS'], mat-option:has-text('iOS'), [role='option']:has-text('iOS')"
    APP_TYPE_TVS = "[value='TV_LIMITED_INPUT'], mat-option:has-text('TVs'), [role='option']:has-text('TVs')"
    APP_TYPE_UWP = "[value='UWP'], mat-option:has-text('Universal Windows'), [role='option']:has-text('Universal Windows')"
    
    NAME_INPUT = "input[aria-label='Name'], input[formcontrolname='name'], input[name='name']"
    
    ADD_URI_BUTTON = "button:has-text('Add URI'), button:has-text('+ Add URI')"
    ORIGIN_INPUT = "input[placeholder*='example.com'], input[aria-label*='JavaScript origin']"
    REDIRECT_URI_INPUT = "input[placeholder*='oauth2callback'], input[aria-label*='redirect URI']"
    
    CREATE_BUTTON = "button:has-text('Create'), button[type='submit']:has-text('Create')"
    SAVE_BUTTON = "button:has-text('Save'), button[type='submit']:has-text('Save')"

    CLIENT_ID_DISPLAY = "cds-copy-to-clipboard[data-id='client-id'], [data-testid='client-id'] code, .client-id code"
    CLIENT_SECRET_DISPLAY = "cds-copy-to-clipboard[data-id='client-secret'], [data-testid='client-secret'] code, .client-secret code"
    CLOSE_DIALOG_BUTTON = "button:has-text('OK'), button:has-text('Close'), button[aria-label='Close']"
    DOWNLOAD_JSON_BUTTON = "button:has-text('Download JSON'), a:has-text('Download JSON')"

    CONSENT_SCREEN_LINK = "a:has-text('OAuth consent screen'), a[href*='consent']"
    CONSENT_INTERNAL_RADIO = "input[value='INTERNAL'], mat-radio-button:has-text('Internal')"
    CONSENT_EXTERNAL_RADIO = "input[value='EXTERNAL'], mat-radio-button:has-text('External')"
    CONSENT_CREATE_BUTTON = "button:has-text('Create'), button[type='submit']"
    
    CONSENT_APP_NAME_INPUT = "input[formcontrolname='appName'], input[aria-label='App name'], input[name='appName']"
    CONSENT_USER_SUPPORT_EMAIL = "input[formcontrolname='supportEmail'], input[aria-label='User support email'], mat-select[formcontrolname='supportEmail']"
    CONSENT_APP_LOGO_UPLOAD = "input[type='file'][accept*='image'], button:has-text('Upload file')"
    CONSENT_HOMEPAGE_URL = "input[formcontrolname='homepageUri'], input[aria-label='Application home page']"
    CONSENT_PRIVACY_POLICY_URL = "input[formcontrolname='privacyPolicyUri'], input[aria-label='Application privacy policy link']"
    CONSENT_TERMS_OF_SERVICE_URL = "input[formcontrolname='tosUri'], input[aria-label='Application terms of service link']"
    CONSENT_AUTHORIZED_DOMAINS = "input[formcontrolname='authorizedDomain'], input[aria-label='Authorized domain']"
    CONSENT_ADD_DOMAIN_BUTTON = "button:has-text('Add Domain'), button:has-text('+ Add domain')"
    CONSENT_DEVELOPER_EMAIL = "input[formcontrolname='developerEmail'], input[aria-label='Developer contact information']"
    CONSENT_ADD_EMAIL_BUTTON = "button:has-text('Add email'), button:has-text('+ Add email')"
    
    SAVE_AND_CONTINUE_BUTTON = "button:has-text('Save and Continue'), button:has-text('Save and continue')"
    BACK_BUTTON = "button:has-text('Back')"
    
    SCOPES_ADD_BUTTON = "button:has-text('Add or Remove Scopes'), button:has-text('Add or remove scopes')"
    SCOPES_FILTER_INPUT = "input[placeholder*='Filter'], input[aria-label*='Filter scopes']"
    SCOPES_CHECKBOX = "mat-checkbox, input[type='checkbox']"
    SCOPES_UPDATE_BUTTON = "button:has-text('Update'), button:has-text('Save')"
    
    TEST_USERS_ADD_BUTTON = "button:has-text('Add Users'), button:has-text('+ Add users')"
    TEST_USERS_INPUT = "input[placeholder*='email'], textarea[placeholder*='email']"
    TEST_USERS_SAVE_BUTTON = "button:has-text('Add'), button:has-text('Save')"
    
    OAUTH_CLIENTS_TABLE = "table, cfc-table, mat-table"
    OAUTH_CLIENT_ROW = "tr, mat-row, [role='row']"
    OAUTH_CLIENT_NAME_CELL = "td:first-child, mat-cell:first-child"
    OAUTH_CLIENT_DELETE_BUTTON = "button:has-text('Delete'), button[aria-label='Delete']"
    OAUTH_CLIENT_EDIT_BUTTON = "button:has-text('Edit'), a:has-text('Edit')"
    
    DELETE_CONFIRM_INPUT = "input[type='text'], input[aria-label*='confirm']"
    DELETE_CONFIRM_BUTTON = "button:has-text('Delete'), button[type='submit']:has-text('Delete')"


@dataclass
class GoogleOAuthConfig:
    name: str
    app_type: str = "web"
    
    javascript_origins: List[str] = field(default_factory=list)
    redirect_uris: List[str] = field(default_factory=list)
    
    homepage_url: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    terms_of_service_url: Optional[str] = None
    
    user_type: str = "external"
    app_logo_path: Optional[str] = None
    user_support_email: Optional[str] = None
    developer_contact_emails: List[str] = field(default_factory=list)
    authorized_domains: List[str] = field(default_factory=list)
    
    scopes: List[str] = field(default_factory=list)
    
    test_users: List[str] = field(default_factory=list)
    
    project_id: Optional[str] = None


@dataclass
class GoogleOAuthCredentials:
    client_id: str
    client_secret: str
    app_name: str
    app_type: str
    project_id: str
    homepage_url: str = ""
    privacy_policy_url: str = ""
    terms_of_service_url: str = ""

    def to_env_string(self) -> str:
        lines = [
            f"",
            f"# Google OAuth Credentials ({self.app_name})",
            f'GOOGLE_CLIENT_ID="{self.client_id}"',
            f'GOOGLE_CLIENT_SECRET="{self.client_secret}"',
            f'GOOGLE_PROJECT_ID="{self.project_id}"',
        ]
        if self.homepage_url:
            lines.append(f'GOOGLE_APP_HOMEPAGE_URL="{self.homepage_url}"')
        if self.privacy_policy_url:
            lines.append(f'GOOGLE_PRIVACY_POLICY_URL="{self.privacy_policy_url}"')
        if self.terms_of_service_url:
            lines.append(f'GOOGLE_TERMS_OF_SERVICE_URL="{self.terms_of_service_url}"')
        return "\n".join(lines) + "\n"

    def to_env_string_with_prefix(self, prefix: str = "") -> str:
        key_prefix = f"{prefix}_" if prefix else ""
        lines = [
            f"",
            f"# Google OAuth Credentials ({self.app_name})",
            f'{key_prefix}GOOGLE_CLIENT_ID="{self.client_id}"',
            f'{key_prefix}GOOGLE_CLIENT_SECRET="{self.client_secret}"',
            f'{key_prefix}GOOGLE_PROJECT_ID="{self.project_id}"',
        ]
        if self.homepage_url:
            lines.append(f'{key_prefix}GOOGLE_APP_HOMEPAGE_URL="{self.homepage_url}"')
        if self.privacy_policy_url:
            lines.append(f'{key_prefix}GOOGLE_PRIVACY_POLICY_URL="{self.privacy_policy_url}"')
        if self.terms_of_service_url:
            lines.append(f'{key_prefix}GOOGLE_TERMS_OF_SERVICE_URL="{self.terms_of_service_url}"')
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict:
        return {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "project_id": self.project_id,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            }
        }

    def verify(self) -> bool:
        logger.info("🔍 Verifying Google OAuth credentials...")

        if not self.client_id.endswith(".apps.googleusercontent.com"):
            logger.warning(f"   ⚠️  Client ID has unexpected format: {self.client_id}")
            return False

        if len(self.client_secret) < 10:
            logger.warning(f"   ⚠️  Client secret seems too short: {len(self.client_secret)} chars")
            return False

        try:
            test_url = f"https://accounts.google.com/o/oauth2/auth?client_id={self.client_id}&response_type=code&scope=openid&redirect_uri=http://localhost"
            req = urllib.request.Request(test_url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 302]:
                    logger.info("   ✅ Client ID is recognized by Google")
                    logger.info("   ✅ Client secret format is valid")
                    logger.info("   ✅ Credentials verified successfully!")
                    return True

        except urllib.error.HTTPError as e:
            if e.code == 400:
                logger.warning("   ⚠️  Invalid client ID or configuration")
                return False
            logger.warning(f"   ⚠️  HTTP {e.code} - verification inconclusive")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not verify: {e}")

        logger.info("   ✅ Credential format looks valid (online verification skipped)")
        return True


class GoogleAutomator:
    def __init__(self, page: Page):
        self.page = page

    def ensure_logged_in(self) -> bool:
        self.page.goto(f"{GoogleSelectors.BASE_URL}/")

        time.sleep(2)

        if self.page.url.startswith("https://accounts.google.com/"):
            logger.info("🔐 Authentication required. Please log in via the browser window.")

            try:
                self.page.wait_for_url(f"**{GoogleSelectors.BASE_URL}/**", timeout=300_000)
                logger.info("✅ Login detected!")
                return True
            except Exception:
                logger.error("❌ Login timed out.")
                return False

        logger.info("✅ Already logged in (session restored)")
        return True

    def select_or_create_project(self, project_id: Optional[str] = None) -> str:
        logger.info(f"📁 Selecting project...")

        self.page.goto(f"{GoogleSelectors.BASE_URL}/home/dashboard")
        
        try:
            # wait for the project selector to be actionable
            project_selector = self.page.wait_for_selector(GoogleSelectors.PROJECT_SELECTOR_BUTTON, state="visible", timeout=10000)
            if project_selector:
                project_selector.click()
        except:
            logger.warning("   ⚠️  Project selector not found or not clickable.")
            return self._get_current_project_id()
            
        time.sleep(1)

        if project_id:
            logger.info(f"   Searching for project: {project_id}")

            try:
                search_input = self.page.wait_for_selector(GoogleSelectors.PROJECT_SEARCH_INPUT, state="visible", timeout=5000)
                if search_input:
                    search_input.fill(project_id)
                    time.sleep(1)

                    # Wait for results
                    self.page.wait_for_selector(GoogleSelectors.PROJECT_ITEM, state="visible", timeout=5000)
                    project_items = self.page.query_selector_all(GoogleSelectors.PROJECT_ITEM)
                    
                    for item in project_items:
                        text = item.inner_text()
                        if project_id.lower() in text.lower():
                            item.click()
                            logger.info(f"   ✅ Selected project: {project_id}")
                            time.sleep(2)
                            return project_id
            except:
                logger.warning(f"   Could not specifically select project {project_id}")

        logger.info("   Please select a project in the browser...")
        try:
            self.page.wait_for_url(f"**{GoogleSelectors.BASE_URL}/home/dashboard**", timeout=60000)
        except:
            pass
            
        return self._get_current_project_id()

    def _get_current_project_id(self) -> str:
        time.sleep(1)
        project_id_match = re.search(r"/project/([^/?]+)", self.page.url)
        if project_id_match:
            return project_id_match.group(1)

        project_indicator = self.page.query_selector("[data-project-id], [data-id*='project']")
        if project_indicator:
            return project_indicator.get_attribute("data-project-id") or "unknown"

        logger.warning("   ⚠️  Could not determine project ID")
        return "unknown"

    def setup_consent_screen(self, config: GoogleOAuthConfig) -> bool:
        logger.info("📝 Checking OAuth consent screen...")

        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials/consent")
        time.sleep(3)

        current_url = self.page.url.lower()
        if "edit" in current_url or "summary" in current_url:
            logger.info("   ✅ Consent screen already configured")
            return True

        app_name_visible = self.page.query_selector("text=App name")
        if app_name_visible:
            logger.info("   ✅ Consent screen already in edit mode")
            return True

        user_type_selector = self.page.query_selector("text=User Type")
        if not user_type_selector:
            logger.info("   ✅ Consent screen appears to be configured")
            return True

        logger.info("   Setting up new consent screen...")
        
        if config.user_type.lower() == "internal":
            internal_radio = self.page.query_selector(GoogleSelectors.CONSENT_INTERNAL_RADIO)
            if internal_radio and internal_radio.is_visible():
                internal_radio.click()
                logger.info("   Selected Internal user type")
        else:
            external_radio = self.page.query_selector(GoogleSelectors.CONSENT_EXTERNAL_RADIO)
            if external_radio and external_radio.is_visible():
                external_radio.click()
                logger.info("   Selected External user type")

        time.sleep(0.5)

        create_btn = self.page.query_selector(GoogleSelectors.CONSENT_CREATE_BUTTON)
        if create_btn and create_btn.is_visible():
            try:
                create_btn.click(timeout=5000)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"   Could not click create: {e}")

        app_name_input = self.page.query_selector(GoogleSelectors.CONSENT_APP_NAME_INPUT)
        if app_name_input and app_name_input.is_visible():
            self._fill_consent_app_info(config)

            save_btn = self.page.query_selector(GoogleSelectors.SAVE_AND_CONTINUE_BUTTON)
            if save_btn and save_btn.is_visible():
                save_btn.click()
                logger.info("   Saved App Information")
                time.sleep(2)

        logger.info("   ✅ Consent screen setup complete")
        return True

    def _fill_consent_app_info(self, config: GoogleOAuthConfig):
        app_name_input = self.page.query_selector(GoogleSelectors.CONSENT_APP_NAME_INPUT)
        if app_name_input:
            app_name_input.fill(config.name)
            time.sleep(0.3)

        support_email = self.page.query_selector(GoogleSelectors.CONSENT_USER_SUPPORT_EMAIL)
        if support_email and config.user_support_email:
            if support_email.get_attribute("role") == "combobox":
                support_email.click()
                time.sleep(0.5)
                option = self.page.query_selector(f"[role='option']:has-text('{config.user_support_email}')")
                if option:
                    option.click()
            else:
                support_email.fill(config.user_support_email)
            time.sleep(0.3)

        if config.app_logo_path and Path(config.app_logo_path).exists():
            logo_input = self.page.query_selector(GoogleSelectors.CONSENT_APP_LOGO_UPLOAD)
            if logo_input:
                logo_input.set_input_files(config.app_logo_path)
                logger.info(f"   Uploaded app logo: {config.app_logo_path}")
                time.sleep(1)

        if config.homepage_url:
            homepage_input = self.page.query_selector(GoogleSelectors.CONSENT_HOMEPAGE_URL)
            if homepage_input:
                homepage_input.fill(config.homepage_url)
                time.sleep(0.3)

        if config.privacy_policy_url:
            privacy_input = self.page.query_selector(GoogleSelectors.CONSENT_PRIVACY_POLICY_URL)
            if privacy_input:
                privacy_input.fill(config.privacy_policy_url)
                time.sleep(0.3)

        if config.terms_of_service_url:
            tos_input = self.page.query_selector(GoogleSelectors.CONSENT_TERMS_OF_SERVICE_URL)
            if tos_input:
                tos_input.fill(config.terms_of_service_url)
                time.sleep(0.3)

        for domain in config.authorized_domains:
            add_btn = self.page.query_selector(GoogleSelectors.CONSENT_ADD_DOMAIN_BUTTON)
            if add_btn:
                add_btn.click()
                time.sleep(0.3)

            domain_inputs = self.page.query_selector_all(GoogleSelectors.CONSENT_AUTHORIZED_DOMAINS)
            if domain_inputs:
                domain_inputs[-1].fill(domain)
                time.sleep(0.3)

        for email in config.developer_contact_emails:
            add_btn = self.page.query_selector(GoogleSelectors.CONSENT_ADD_EMAIL_BUTTON)
            if add_btn:
                add_btn.click()
                time.sleep(0.3)

            email_inputs = self.page.query_selector_all(GoogleSelectors.CONSENT_DEVELOPER_EMAIL)
            if email_inputs:
                email_inputs[-1].fill(email)
                time.sleep(0.3)

    def _configure_scopes(self, config: GoogleOAuthConfig):
        if not config.scopes:
            return

        add_scopes_btn = self.page.query_selector(GoogleSelectors.SCOPES_ADD_BUTTON)
        if not add_scopes_btn:
            return

        add_scopes_btn.click()
        time.sleep(1)

        for scope in config.scopes:
            filter_input = self.page.query_selector(GoogleSelectors.SCOPES_FILTER_INPUT)
            if filter_input:
                filter_input.fill(scope)
                time.sleep(0.5)

            checkboxes = self.page.query_selector_all(GoogleSelectors.SCOPES_CHECKBOX)
            for checkbox in checkboxes:
                if not checkbox.is_checked():
                    checkbox.click()
                    time.sleep(0.2)

        update_btn = self.page.query_selector(GoogleSelectors.SCOPES_UPDATE_BUTTON)
        if update_btn:
            update_btn.click()
            time.sleep(1)

    def _add_test_users(self, test_users: List[str]):
        if not test_users:
            return

        add_btn = self.page.query_selector(GoogleSelectors.TEST_USERS_ADD_BUTTON)
        if not add_btn:
            return

        add_btn.click()
        time.sleep(0.5)

        users_input = self.page.query_selector(GoogleSelectors.TEST_USERS_INPUT)
        if users_input:
            users_input.fill(",".join(test_users))
            time.sleep(0.3)

        save_btn = self.page.query_selector(GoogleSelectors.TEST_USERS_SAVE_BUTTON)
        if save_btn:
            save_btn.click()
            logger.info(f"   Added {len(test_users)} test user(s)")
            time.sleep(1)

    def create_oauth_client(self, config: GoogleOAuthConfig) -> GoogleOAuthCredentials:
        project_id = self.select_or_create_project(config.project_id)

        logger.info(f"📝 Creating OAuth client: {config.name}")

        self.setup_consent_screen(config)

        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials")
        
        try:
            create_btn = self.page.wait_for_selector(GoogleSelectors.CREATE_CREDENTIALS_BUTTON, state="visible", timeout=15000)
            if not create_btn:
                raise Exception("Could not find 'Create Credentials' button")
            create_btn.click()
        except Exception as e:
            raise Exception(f"Failed to click Create Credentials: {e}")

        try:
            oauth_option = self.page.wait_for_selector(GoogleSelectors.OAUTH_CLIENT_ID_OPTION, state="visible", timeout=5000)
            if not oauth_option:
                raise Exception("Could not find 'OAuth client ID' option")
            oauth_option.click()
        except:
             # Fallback for small screens or different menus
             time.sleep(1)
             oauth_option = self.page.query_selector(GoogleSelectors.OAUTH_CLIENT_ID_OPTION)
             if oauth_option:
                 oauth_option.click()
             else:
                 raise

        time.sleep(2)

        self._select_app_type(config.app_type)
        time.sleep(0.5)

        try:
            name_input = self.page.wait_for_selector(GoogleSelectors.NAME_INPUT, state="visible", timeout=5000)
            if name_input:
                name_input.fill(config.name)
        except:
            pass

        if config.app_type.lower() == "web":
            self._add_javascript_origins(config.javascript_origins)
            self._add_redirect_uris(config.redirect_uris)

        try:
            create_button = self.page.wait_for_selector(GoogleSelectors.CREATE_BUTTON, state="visible", timeout=5000)
            if not create_button:
                raise Exception("Could not find Create button")
            create_button.click()
        except Exception as e:
             raise Exception(f"Failed to click Create button: {e}")
             
        logger.info("   Submitting OAuth client creation...")
        time.sleep(3)

        client_id = self._extract_client_id()
        client_secret = self._extract_client_secret()
        
        # Close the dialog
        try:
             close_button = self.page.query_selector(GoogleSelectors.CLOSE_DIALOG_BUTTON)
             if close_button:
                 close_button.click()
        except:
             pass

        return GoogleOAuthCredentials(
            client_id=client_id,
            client_secret=client_secret,
            app_name=config.name,
            app_type=config.app_type,
            project_id=project_id,
            homepage_url=config.homepage_url or "",
            privacy_policy_url=config.privacy_policy_url or "",
            terms_of_service_url=config.terms_of_service_url or "",
        )

    def _select_app_type(self, app_type: str):
        dropdown = self.page.query_selector(GoogleSelectors.APP_TYPE_DROPDOWN)
        if dropdown:
            dropdown.click()
            time.sleep(0.5)

        type_map = {
            "web": GoogleSelectors.APP_TYPE_WEB,
            "desktop": GoogleSelectors.APP_TYPE_DESKTOP,
            "android": GoogleSelectors.APP_TYPE_ANDROID,
            "ios": GoogleSelectors.APP_TYPE_IOS,
            "tvs": GoogleSelectors.APP_TYPE_TVS,
            "uwp": GoogleSelectors.APP_TYPE_UWP,
        }

        selector = type_map.get(app_type.lower(), GoogleSelectors.APP_TYPE_WEB)
        option = self.page.query_selector(selector)
        if option:
            option.click()
            time.sleep(0.5)

    def _add_javascript_origins(self, origins: List[str]):
        if not origins:
            return
            
        for i, origin in enumerate(origins):
            origin_inputs = self.page.query_selector_all("input[type='url'], input[type='text']")
            js_origin_section = self.page.query_selector("text=Authorized JavaScript origins")
            
            if js_origin_section:
                section_parent = js_origin_section.evaluate("el => el.closest('div')")
            
            empty_inputs = []
            all_inputs = self.page.query_selector_all("input")
            for inp in all_inputs:
                try:
                    value = inp.input_value()
                    placeholder = inp.get_attribute("placeholder") or ""
                    if not value and "example.com" in placeholder.lower():
                        empty_inputs.append(inp)
                except:
                    pass
            
            if i == 0 and empty_inputs:
                empty_inputs[0].fill(origin)
                logger.info(f"   Added JavaScript origin: {origin}")
                time.sleep(0.3)
            else:
                add_btns = self.page.query_selector_all("button:has-text('Add URI'), button:has-text('+ Add URI')")
                if add_btns:
                    add_btns[0].click()
                    time.sleep(0.5)
                    
                    new_inputs = []
                    all_inputs = self.page.query_selector_all("input")
                    for inp in all_inputs:
                        try:
                            value = inp.input_value()
                            if not value:
                                new_inputs.append(inp)
                        except:
                            pass
                    
                    if new_inputs:
                        new_inputs[-1].fill(origin)
                        logger.info(f"   Added JavaScript origin: {origin}")
                        time.sleep(0.3)

    def _add_redirect_uris(self, uris: List[str]):
        if not uris:
            return
            
        redirect_section = self.page.query_selector("text=Authorized redirect URIs")
        if not redirect_section:
            logger.warning("   Could not find redirect URIs section")
            return
            
        for i, uri in enumerate(uris):
            add_btns = self.page.query_selector_all("button:has-text('Add URI'), button:has-text('+ Add URI')")
            
            redirect_add_btn = None
            for btn in add_btns:
                try:
                    btn_box = btn.bounding_box()
                    section_box = redirect_section.bounding_box()
                    if btn_box and section_box and btn_box["y"] > section_box["y"]:
                        redirect_add_btn = btn
                        break
                except:
                    pass
            
            if redirect_add_btn:
                redirect_add_btn.click()
                time.sleep(0.5)
            
            empty_inputs = []
            all_inputs = self.page.query_selector_all("input")
            for inp in all_inputs:
                try:
                    value = inp.input_value()
                    if not value:
                        inp_box = inp.bounding_box()
                        section_box = redirect_section.bounding_box()
                        if inp_box and section_box and inp_box["y"] > section_box["y"]:
                            empty_inputs.append(inp)
                except:
                    pass
            
            if empty_inputs:
                empty_inputs[-1].fill(uri)
                logger.info(f"   Added redirect URI: {uri}")
                time.sleep(0.3)

    def _extract_client_id(self) -> str:
        for _ in range(10):
            try:
                client_id_el = self.page.query_selector(GoogleSelectors.CLIENT_ID_DISPLAY)
                if client_id_el:
                    text = client_id_el.inner_text().strip()
                    if ".apps.googleusercontent.com" in text:
                        return text
            except Exception:
                pass
            time.sleep(0.5)

        codes = self.page.query_selector_all("code")
        for code in codes:
            text = code.inner_text().strip()
            if ".apps.googleusercontent.com" in text:
                return text

        raise Exception("Could not extract Client ID from the page")

    def _extract_client_secret(self) -> str:
        for _ in range(10):
            try:
                client_secret_el = self.page.query_selector(GoogleSelectors.CLIENT_SECRET_DISPLAY)
                if client_secret_el:
                    text = client_secret_el.inner_text().strip()
                    if text and len(text) > 10:
                        return text
            except Exception:
                pass
            time.sleep(0.5)

        codes = self.page.query_selector_all("code")
        for code in codes:
            text = code.inner_text().strip()
            if text and len(text) > 20 and ".apps.googleusercontent.com" not in text:
                return text

        raise Exception("Could not extract Client Secret from the page")

    def list_oauth_clients(self) -> List[Dict]:
        logger.info("📋 Fetching OAuth clients list...")
        self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials")
        time.sleep(2)

        clients = []

        rows = self.page.query_selector_all(f"{GoogleSelectors.OAUTH_CLIENTS_TABLE} {GoogleSelectors.OAUTH_CLIENT_ROW}")
        
        for row in rows:
            try:
                name_cell = row.query_selector(GoogleSelectors.OAUTH_CLIENT_NAME_CELL)
                if name_cell:
                    name = name_cell.inner_text().strip()
                    if name and name != "Name":
                        href = row.query_selector("a")
                        url = href.get_attribute("href") if href else ""
                        clients.append({
                            "name": name,
                            "url": url,
                        })
            except Exception:
                continue

        logger.info(f"   Found {len(clients)} OAuth client(s)")
        return clients

    def delete_oauth_client(self, client_name: str) -> bool:
        logger.info(f"🗑️  Deleting OAuth client: {client_name}")

        try:
            self.page.goto(f"{GoogleSelectors.BASE_URL}/apis/credentials")
            time.sleep(2)

            rows = self.page.query_selector_all(f"{GoogleSelectors.OAUTH_CLIENTS_TABLE} {GoogleSelectors.OAUTH_CLIENT_ROW}")
            
            for row in rows:
                name_cell = row.query_selector(GoogleSelectors.OAUTH_CLIENT_NAME_CELL)
                if name_cell and client_name.lower() in name_cell.inner_text().strip().lower():
                    delete_btn = row.query_selector(GoogleSelectors.OAUTH_CLIENT_DELETE_BUTTON)
                    if delete_btn:
                        delete_btn.click()
                        time.sleep(1)

                        confirm_input = self.page.query_selector(GoogleSelectors.DELETE_CONFIRM_INPUT)
                        if confirm_input:
                            confirm_input.fill("DELETE")
                            time.sleep(0.3)

                        confirm_btn = self.page.query_selector(GoogleSelectors.DELETE_CONFIRM_BUTTON)
                        if confirm_btn:
                            confirm_btn.click()
                            logger.info(f"   ✅ Deleted {client_name}")
                            time.sleep(2)
                            return True

            logger.warning(f"   ⚠️  Could not find client: {client_name}")
            return False

        except Exception as e:
            logger.error(f"   ❌ Deletion failed: {e}")
            return False


def get_last_commit_date() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=short"],
            capture_output=True, text=True, cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "unknown"


from version_check import CURRENT_VERSION

def print_banner():
    last_updated = get_last_commit_date()
    # Use centralized version from pyproject.toml via version_check
    version = f"v{CURRENT_VERSION}"
    banner = f"""
\033[38;5;39m
   ██████╗  ██████╗  ██████╗  ██████╗ ██╗     ███████╗
  ██╔════╝ ██╔═══██╗██╔═══██╗██╔════╝ ██║     ██╔════╝
  ██║  ███╗██║   ██║██║   ██║██║  ███╗██║     █████╗  
  ██║   ██║██║   ██║██║   ██║██║   ██║██║     ██╔══╝  
  ╚██████╔╝╚██████╔╝╚██████╔╝╚██████╔╝███████╗███████╗
   ╚═════╝  ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚══════╝
\033[0m
  \033[1m🔐 OAuth Automator\033[0m \033[90m{version} • Updated {last_updated}\033[0m
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
  \033[36mAutomate Google OAuth client creation with full
  consent screen configuration & credential management.\033[0m
  
  \033[90mBy @remcostoeten • github.com/remcostoeten\033[0m
"""
    print(banner)


def prompt_list(prompt_text: str, default: str = "") -> List[str]:
    print(f"\033[94m➤\033[0m {prompt_text}")
    if default:
        print(f"   \033[90m(default: {default})\033[0m")
    value = input("   Enter comma-separated values: ").strip()
    if not value and default:
        return [x.strip() for x in default.split(",") if x.strip()]
    return [x.strip() for x in value.split(",") if x.strip()]


def interactive_create():
    print("\n\033[1m📝 Create New Google OAuth Application\033[0m")
    print("\033[90m" + "─" * 50 + "\033[0m\n")

    from dotenv import load_dotenv
    load_dotenv()

    default_app_name = os.getenv("GOOGLE_OAUTH_APP_NAME", "my-google-app")
    default_homepage = os.getenv("OAUTH_BASE_URL", "http://localhost:3000")
    default_user_type = os.getenv("GOOGLE_USER_TYPE", "external")
    default_support_email = os.getenv("GOOGLE_USER_SUPPORT_EMAIL", "")
    default_privacy = os.getenv("GOOGLE_PRIVACY_POLICY_URL", "")
    default_tos = os.getenv("GOOGLE_TERMS_OF_SERVICE_URL", "")
    default_scopes = os.getenv("GOOGLE_OAUTH_SCOPES", "email,profile,openid")
    default_test_users = os.getenv("GOOGLE_TEST_USERS", "")
    default_dev_emails = os.getenv("GOOGLE_DEVELOPER_CONTACT_EMAILS", "")

    print("\033[93m┌─ Basic Information ─────────────────────────────┐\033[0m")
    app_name = prompt("Application name", default_app_name)
    app_type = prompt("Application type (web/desktop/android/ios)", "web").lower()
    homepage_url = prompt("Homepage URL", default_homepage).rstrip("/")

    default_callback = f"{homepage_url}/api/auth/callback/google"
    callback_url = prompt("Callback URL", default_callback)
    print("\033[93m└─────────────────────────────────────────────────┘\033[0m\n")

    print("\033[93m┌─ Consent Screen Configuration ─────────────────┐\033[0m")
    user_type = prompt("User type (internal/external)", default_user_type).lower()
    user_support_email = prompt("User support email", default_support_email)
    privacy_policy_url = prompt("Privacy policy URL (optional)", default_privacy)
    terms_of_service_url = prompt("Terms of service URL (optional)", default_tos)
    print("\033[93m└─────────────────────────────────────────────────┘\033[0m\n")

    print("\033[93m┌─ Developer Information ────────────────────────┐\033[0m")
    developer_emails = prompt_list("Developer contact emails", default_dev_emails)
    print("\033[93m└─────────────────────────────────────────────────┘\033[0m\n")

    print("\033[93m┌─ OAuth Scopes ─────────────────────────────────┐\033[0m")
    scopes = prompt_list("OAuth scopes", default_scopes)
    print("\033[93m└─────────────────────────────────────────────────┘\033[0m\n")

    if user_type == "external":
        print("\033[93m┌─ Test Users (External Apps) ──────────────────┐\033[0m")
        test_users = prompt_list("Test user emails", default_test_users)
        print("\033[93m└─────────────────────────────────────────────────┘\033[0m\n")
    else:
        test_users = []

    javascript_origins = []
    redirect_uris = []

    if app_type == "web":
        javascript_origins.append(homepage_url)

    redirect_uris.append(callback_url)

    copy_clipboard, write_env, env_file = prompt_output_options()

    print("\n\033[90m" + "─" * 50 + "\033[0m")
    print("\033[1m📋 Configuration Summary:\033[0m")
    print(f"   • App Name:           \033[96m{app_name}\033[0m")
    print(f"   • Type:               \033[96m{app_type}\033[0m")
    print(f"   • User Type:          \033[96m{user_type}\033[0m")
    print(f"   • Homepage:           \033[96m{homepage_url}\033[0m")
    print(f"   • Callback:           \033[96m{callback_url}\033[0m")
    print(f"   • Support Email:      \033[96m{user_support_email or 'Not set'}\033[0m")
    print(f"   • Privacy Policy:     \033[96m{privacy_policy_url or 'Not set'}\033[0m")
    print(f"   • Terms of Service:   \033[96m{terms_of_service_url or 'Not set'}\033[0m")
    print(f"   • Developer Emails:   \033[96m{', '.join(developer_emails) or 'Not set'}\033[0m")
    print(f"   • Scopes:             \033[96m{', '.join(scopes)}\033[0m")
    if test_users:
        print(f"   • Test Users:         \033[96m{', '.join(test_users)}\033[0m")
    print(f"   • Clipboard:          \033[96m{'Yes' if copy_clipboard else 'No'}\033[0m")
    print(f"   • Write to:           \033[96m{env_file if write_env else 'None'}\033[0m")
    print("\033[90m" + "─" * 50 + "\033[0m\n")

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
            homepage_url=homepage_url,
            privacy_policy_url=privacy_policy_url if privacy_policy_url else None,
            terms_of_service_url=terms_of_service_url if terms_of_service_url else None,
            user_type=user_type,
            user_support_email=user_support_email if user_support_email else None,
            developer_contact_emails=developer_emails,
            scopes=scopes,
            test_users=test_users,
        )
        creds = automator.create_oauth_client(config)

        print("\n\033[92m" + "─" * 60)
        print(" SUCCESS: Application Created Successfully")
        print("─" * 60 + "\033[0m")
        print(creds.to_env_string())

        creds.verify()

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


def interactive_list():
    print("\n\033[1m📋 List Google OAuth Clients\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GoogleAutomator(page)

        if not automator.ensure_logged_in():
            return

        clients = automator.list_oauth_clients()

        if not clients:
            print("\033[93m   No OAuth clients found.\033[0m")
        else:
            print("\n\033[1m   OAuth Clients:\033[0m")
            for i, client in enumerate(clients, 1):
                print(f"   {i}. \033[96m{client['name']}\033[0m")

        input("\nPress Enter to close browser...")

    except Exception as e:
        logger.error(f"Failed: {e}")

    finally:
        browser_mgr.close()


def interactive_delete():
    print("\n\033[1m🗑️  Delete Google OAuth Client\033[0m")
    print("\033[90m" + "─" * 40 + "\033[0m\n")

    client_name = prompt("OAuth client name to delete", "")
    if not client_name:
        print("\033[93m⚠️  No name provided. Cancelled.\033[0m")
        return

    if not prompt_yes_no(f"Are you sure you want to delete '{client_name}'?", False):
        print("\033[93m⚠️  Cancelled.\033[0m")
        return

    browser_mgr = BrowserManager(headless=False)

    try:
        page = browser_mgr.start()
        automator = GoogleAutomator(page)

        if not automator.ensure_logged_in():
            return

        automator.delete_oauth_client(client_name)

        input("\nPress Enter to close browser...")

    except Exception as e:
        logger.error(f"Failed: {e}")

    finally:
        browser_mgr.close()


def prompt_output_options() -> tuple:
    print("\n\033[93m┌─────────────────────────────────────┐\033[0m")
    print("\033[93m│\033[0m  \033[1mHow to save credentials?\033[0m          \033[93m│\033[0m")
    print("\033[93m├─────────────────────────────────────┤\033[0m")
    print("\033[93m│\033[0m  \033[92m1.\033[0m Copy to clipboard              \033[93m│\033[0m")
    print("\033[93m│\033[0m  \033[92m2.\033[0m Write to .env file             \033[93m│\033[0m")
    print("\033[93m│\033[0m  \033[92m3.\033[0m Both (clipboard + .env)        \033[93m│\033[0m")
    print("\033[93m│\033[0m  \033[92m4.\033[0m Just display (no save)         \033[93m│\033[0m")
    print("\033[93m└─────────────────────────────────────┘\033[0m")
    choice = input("\033[94m➤\033[0m Enter choice (1-4): ").strip()

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
    env_path = Path(env_file)

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


def print_main_menu():
    menu = """
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
  \033[1mSelect an action:\033[0m
  
    \033[38;5;39m❯\033[0m \033[1m1\033[0m  Create new OAuth client
    \033[38;5;39m❯\033[0m \033[1m2\033[0m  List existing OAuth clients  
    \033[38;5;39m❯\033[0m \033[1m3\033[0m  Delete an OAuth client
    \033[38;5;39m❯\033[0m \033[1m4\033[0m  Check for updates
    \033[38;5;39m❯\033[0m \033[1m5\033[0m  Exit
  
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
"""
    print(menu)


def main():
    if len(sys.argv) == 1:
        print_banner()
        print_update_notice()
        
        while True:
            print_main_menu()
            choice = input("\033[94m➤\033[0m Enter choice (1-5): ").strip()
            
            if choice == "1":
                interactive_create()
            elif choice == "2":
                interactive_list()
            elif choice == "3":
                interactive_delete()
            elif choice == "4":
                check_and_update()
            elif choice == "5":
                print("\n\033[96mGoodbye! 👋\033[0m\n")
                break
            else:
                print("\033[91mInvalid choice. Please enter 1-5.\033[0m")
        return

    parser = argparse.ArgumentParser(
        description="Google OAuth Automator - Full Feature Set",
        epilog="Run without arguments for interactive mode.",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    create_parser = subparsers.add_parser("create", help="Create a new OAuth client")
    create_parser.add_argument("--app-name", required=True, help="Name of the OAuth application")
    create_parser.add_argument("--app-type", default="web", choices=["web", "desktop", "android", "ios", "tvs", "uwp"], help="Application type")
    create_parser.add_argument("--homepage-url", default="http://localhost:3000", help="Homepage URL")
    create_parser.add_argument("--callback-url", help="Callback URL (defaults to homepage + /api/auth/callback/google)")
    create_parser.add_argument("--user-type", default="external", choices=["internal", "external"], help="User type for consent screen")
    create_parser.add_argument("--support-email", help="User support email")
    create_parser.add_argument("--privacy-policy-url", help="Privacy policy URL")
    create_parser.add_argument("--terms-of-service-url", help="Terms of service URL")
    create_parser.add_argument("--developer-emails", help="Developer contact emails (comma-separated)")
    create_parser.add_argument("--scopes", default="email,profile,openid", help="OAuth scopes (comma-separated)")
    create_parser.add_argument("--test-users", help="Test user emails (comma-separated)")
    create_parser.add_argument("--write-env", action="store_true", help="Append credentials to .env file")
    create_parser.add_argument("--project-id", help="Google Cloud project ID (optional)")
    
    list_parser = subparsers.add_parser("list", help="List existing OAuth clients")
    
    delete_parser = subparsers.add_parser("delete", help="Delete an OAuth client")
    delete_parser.add_argument("--name", required=True, help="Name of the OAuth client to delete")

    args = parser.parse_args()

    if args.command == "list":
        browser_mgr = BrowserManager(headless=False)
        try:
            page = browser_mgr.start()
            automator = GoogleAutomator(page)
            if automator.ensure_logged_in():
                clients = automator.list_oauth_clients()
                for client in clients:
                    print(f"  - {client['name']}")
        finally:
            browser_mgr.close()
        return

    if args.command == "delete":
        browser_mgr = BrowserManager(headless=False)
        try:
            page = browser_mgr.start()
            automator = GoogleAutomator(page)
            if automator.ensure_logged_in():
                automator.delete_oauth_client(args.name)
        finally:
            browser_mgr.close()
        return

    if args.command == "create":
        callback_url = args.callback_url or f"{args.homepage_url}/api/auth/callback/google"

        javascript_origins = []
        redirect_uris = []

        if args.app_type == "web":
            javascript_origins.append(args.homepage_url)

        redirect_uris.append(callback_url)

        developer_emails = [e.strip() for e in args.developer_emails.split(",")] if args.developer_emails else []
        scopes = [s.strip() for s in args.scopes.split(",")] if args.scopes else []
        test_users = [u.strip() for u in args.test_users.split(",")] if args.test_users else []

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
                homepage_url=args.homepage_url,
                privacy_policy_url=args.privacy_policy_url,
                terms_of_service_url=args.terms_of_service_url,
                user_type=args.user_type,
                user_support_email=args.support_email,
                developer_contact_emails=developer_emails,
                scopes=scopes,
                test_users=test_users,
                project_id=args.project_id,
            )
            creds = automator.create_oauth_client(config)

            print("\n" + "🎉" * 20)
            print("SUCCESS! Application Created.")
            print(creds.to_env_string())

            creds.verify()

            if args.write_env:
                write_google_credentials_to_env(creds, ".env")

            time.sleep(3)

        except Exception as e:
            logger.error(f"Automation failed: {e}")
            input("Press Enter to close browser...")

        finally:
            browser_mgr.close()
        return

    print_banner()
    interactive_create()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n\033[93m👋 Operation cancelled by user. Exiting...\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[91m❌ Unexpected error: {e}\033[0m")
        sys.exit(1)
