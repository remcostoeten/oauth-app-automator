import time
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from playwright.sync_api import Page

from ..core import setup_logger
from .selectors import GitHubSelectors
from .config import OAuthConfig, OAuthCredentials

logger = setup_logger("oauth_automator.github.automator")


class GitHubAutomator:
    def __init__(self, page: Page, password: Optional[str] = None):
        self.page = page
        self.password = password

    def ensure_logged_in(self) -> bool:
        self.page.goto("https://github.com/settings/developers")

        if "/login" in self.page.url or self.page.query_selector(GitHubSelectors.LOGIN_INPUT):
            logger.info("🔐 Authentication required. Please log in via the browser window.")
            try:
                self.page.wait_for_selector(GitHubSelectors.LOGGED_IN_META, timeout=300_000)
                logger.info("✅ Login detected!")
                return True
            except Exception:
                logger.error("❌ Login timed out.")
                return False

        logger.info("✅ Already logged in (session restored)")
        return True

    def handle_sudo_mode(self):
        time.sleep(1)
        is_passkey = any(self.page.query_selector(s) for s in GitHubSelectors.PASSKEY_INDICATORS)

        if is_passkey:
            logger.info("🔐 Passkey authentication detected, clicking 'Use your password'...")
            clicked = False
            for selector in GitHubSelectors.PASSWORD_LINK_SELECTORS:
                try:
                    link = self.page.query_selector(selector)
                    if link and link.is_visible():
                        link.click()
                        clicked = True
                        logger.info("   Switched to password authentication")
                        time.sleep(1)
                        break
                except Exception:
                    continue

        password_field = self.page.query_selector(GitHubSelectors.PASSWORD_INPUT)

        if password_field and password_field.is_visible():
            if self.password:
                logger.info("🔐 Entering password automatically...")
                password_field.fill(self.password)
                for selector in GitHubSelectors.SUBMIT_BUTTONS:
                    try:
                        btn = self.page.query_selector(selector)
                        if btn and btn.is_visible():
                            btn.click()
                            logger.info("   Submitted password form")
                            break
                    except Exception:
                        continue
                
                try:
                    self.page.wait_for_selector(GitHubSelectors.PASSWORD_INPUT, state="detached", timeout=10_000)
                    logger.info("✅ Sudo mode passed!")
                except:
                    logger.warning("   Password field still visible, may need manual intervention")
            else:
                logger.warning("🔐 GitHub Sudo Mode detected (password confirmation).")
                logger.warning("   No --password provided. Please enter your password in the browser...")
                try:
                    self.page.wait_for_selector(GitHubSelectors.PASSWORD_INPUT, state="detached", timeout=300_000)
                    logger.info("✅ Sudo mode passed!")
                except:
                    logger.error("❌ Timed out waiting for sudo mode confirmation.")
                    raise TimeoutError("Sudo mode timeout")

    def list_oauth_apps(self, refresh: bool = False) -> List[dict]:
        logger.info("📋 Fetching OAuth apps list...")
        self.page.goto("https://github.com/settings/developers")
        self.handle_sudo_mode()
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(0.25)

        first_page_apps = self._extract_apps_from_page()
        first_page_ids = [a.get("id", "") for a in first_page_apps if a.get("id")]
        cached = self._load_apps_cache()

        if (not refresh) and cached and self._cache_is_fresh(cached) and cached.get("first_page_ids") == first_page_ids:
            apps = cached.get("apps", [])
            logger.info(f"   Using cached app list ({len(apps)} apps).")
            self._print_apps(apps)
            return apps

        apps = self._scan_all_oauth_apps(first_page_apps=first_page_apps)

        if cached:
            self._log_app_diff(cached.get("apps", []), apps)

        self._save_apps_cache(apps=apps, first_page_ids=first_page_ids)
        return apps

    def _scan_all_oauth_apps(self, first_page_apps: Optional[List[dict]] = None) -> List[dict]:
        apps: List[dict] = []
        page_num = 1

        while True:
            logger.info(f"   Scanning page {page_num}...")
            page_apps = first_page_apps if page_num == 1 and first_page_apps is not None else self._extract_apps_from_page()
            found_on_page = 0
            for app in page_apps:
                if not any(existing["url"] == app["url"] for existing in apps):
                    apps.append(app)
                    found_on_page += 1

            logger.info(f"   Found {found_on_page} apps on page {page_num}")

            next_btn = self.page.query_selector(GitHubSelectors.NEXT_PAGE_LINK)
            if next_btn and next_btn.is_visible():
                next_btn.click()
                self.page.wait_for_load_state("domcontentloaded")
                time.sleep(0.2)
                page_num += 1
            else:
                break

        self._print_apps(apps)
        return apps

    def _print_apps(self, apps: List[dict]) -> None:
        logger.info(f"   Total found: {len(apps)} OAuth app(s)")
        print(f"\nFound {len(apps)} apps:")
        for i, app in enumerate(apps, 1):
            app_id = app.get("id") or "unknown"
            print(f"{i}. [{app_id}] {app['name']} ({app['url']})")

    def find_oauth_apps_by_name(self, app_name_query: str, refresh: bool = False) -> List[dict]:
        logger.info(f"📋 Searching OAuth apps for name: {app_name_query}")
        apps = self.list_oauth_apps(refresh=refresh)
        query = app_name_query.lower()
        exact_matches: List[dict] = []
        partial_matches: List[dict] = []
        for app in apps:
            name_lower = app["name"].lower()
            if name_lower == query:
                exact_matches.append(app)
            elif query in name_lower:
                partial_matches.append(app)

        if exact_matches:
            logger.info(f"   Found exact match(es): {len(exact_matches)}")
            return exact_matches

        logger.info(f"   Found partial match(es): {len(partial_matches)}")
        return partial_matches

    def _extract_apps_from_page(self) -> List[dict]:
        page_apps: List[dict] = []
        for selector in GitHubSelectors.APP_LINKS:
            app_elements = self.page.query_selector_all(selector)
            for el in app_elements:
                href = el.get_attribute("href")
                if not href or "/new" in href or href.endswith("/settings/applications"):
                    continue

                path_parts = href.split("/")
                if len(path_parts) < 4 or not path_parts[-1].isdigit():
                    continue

                name = el.inner_text().strip()
                if not name:
                    continue

                app_url = f"https://github.com{href}" if href.startswith("/") else href
                app_id = self._extract_app_id_from_url(app_url)
                page_apps.append({"id": app_id, "name": name, "url": app_url})
        return page_apps

    def inspect_oauth_app_usage(self, app: dict) -> dict:
        app_name = app.get("name", "Unknown")
        app_url = app.get("url", "")
        app_id = app.get("id", self._extract_app_id_from_url(app_url))

        self.page.goto(app_url, timeout=20_000, wait_until="domcontentloaded")
        self.handle_sudo_mode()
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(0.2)

        body_text = self.page.inner_text("body")
        authorized_users = self._extract_authorized_users(body_text)
        created_at = self._extract_created_date(body_text)

        return {
            "id": app_id,
            "name": app_name,
            "url": app_url,
            "created_at": created_at or "unknown",
            "authorized_users": authorized_users,
            "usage_known": authorized_users is not None,
            "is_unused": authorized_users == 0 if authorized_users is not None else None,
        }

    def inspect_all_oauth_apps_usage(self, apps: List[dict]) -> List[dict]:
        inspected = []
        total = len(apps)
        for idx, app in enumerate(apps, 1):
            logger.info(f"   Inspecting app {idx}/{total}: {app.get('name', 'Unknown')}")
            try:
                inspected.append(self.inspect_oauth_app_usage(app))
            except Exception as e:
                logger.warning(f"   Could not inspect '{app.get('name', 'Unknown')}': {e}")
                inspected.append(
                    {
                        "id": app.get("id", ""),
                        "name": app.get("name", "Unknown"),
                        "url": app.get("url", ""),
                        "created_at": "unknown",
                        "authorized_users": None,
                        "usage_known": False,
                        "is_unused": None,
                    }
                )
        return inspected

    def _extract_authorized_users(self, text: str) -> Optional[int]:
        lowered = text.lower()

        if re.search(r"authorized by\s+no\s+users", lowered):
            return 0
        if re.search(r"has\s+no\s+authorized\s+users", lowered):
            return 0

        match = re.search(r"authorized by\s+([\d,]+)\s+users?", lowered)
        if match:
            return int(match.group(1).replace(",", ""))

        match = re.search(r"([\d,]+)\s+authorized\s+users?", lowered)
        if match:
            return int(match.group(1).replace(",", ""))

        return None

    def _extract_created_date(self, text: str) -> str:
        patterns = [
            r"created on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"created\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"created at\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _apps_cache_path(self) -> Path:
        cache_dir = Path.home() / ".oauth-automator" / "github"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "apps_cache.json"

    def _load_apps_cache(self) -> Optional[dict]:
        path = self._apps_cache_path()
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _save_apps_cache(self, apps: List[dict], first_page_ids: List[str]) -> None:
        path = self._apps_cache_path()
        payload = {
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "first_page_ids": first_page_ids,
            "apps": apps,
        }
        try:
            path.write_text(json.dumps(payload, indent=2))
        except Exception as e:
            logger.warning(f"   Could not write cache: {e}")

    def _cache_is_fresh(self, cache: dict, max_age_seconds: int = 1800) -> bool:
        scanned_at = cache.get("scanned_at")
        if not scanned_at:
            return False
        try:
            ts = datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            return age <= max_age_seconds
        except Exception:
            return False

    def _log_app_diff(self, old_apps: List[dict], new_apps: List[dict]) -> None:
        old_ids = {a.get("id", "") for a in old_apps}
        new_ids = {a.get("id", "") for a in new_apps}
        added = [a for a in new_apps if a.get("id", "") not in old_ids]
        removed = [a for a in old_apps if a.get("id", "") not in new_ids]
        if not added and not removed:
            logger.info("   No app changes since last cached scan.")
            return
        logger.info(f"   App diff: +{len(added)} added, -{len(removed)} removed")

    def _extract_app_id_from_url(self, url: str) -> str:
        match = re.search(r"/settings/applications/(\d+)", url)
        return match.group(1) if match else ""

    def grab_oauth_credentials(self, app_url: str, app_name: str, generate_secret_if_missing: bool = False) -> OAuthCredentials:
        logger.info(f"🔎 Opening app: {app_name}")
        self.page.goto(app_url, timeout=20_000, wait_until="domcontentloaded")
        self.handle_sudo_mode()
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)

        client_id_node = self.page.wait_for_selector(GitHubSelectors.CLIENT_ID_DISPLAY, timeout=10_000)
        client_id = client_id_node.inner_text().strip()

        client_secret = self._extract_visible_secret(client_id)
        if not client_secret and generate_secret_if_missing:
            logger.info("🔐 Existing secret not visible. Generating a new client secret...")
            self._generate_secret()
            client_secret = self._capture_secret(client_id)

        return OAuthCredentials(
            client_id=client_id,
            client_secret=client_secret,
            app_name=app_name,
            app_url=app_url,
        )

    def _extract_visible_secret(self, client_id: str) -> str:
        secret_like = re.compile(r"^[A-Za-z0-9_\-]{20,}$")
        for selector in ("code", "input[type='text']", "input[readonly]", "textarea"):
            elements = self.page.query_selector_all(selector)
            for el in elements:
                value = ""
                try:
                    if selector.startswith("input"):
                        value = (el.get_attribute("value") or "").strip()
                    elif selector == "textarea":
                        value = (el.input_value() or "").strip()
                    else:
                        value = (el.inner_text() or "").strip()
                except Exception:
                    continue

                if not value or value == client_id:
                    continue
                if secret_like.match(value):
                    return value
        return ""

    def delete_oauth_app(self, app_name_query: str) -> bool:
        apps = self.list_oauth_apps()
        target_app = next((a for a in apps if app_name_query.lower() in a["name"].lower()), None)
        
        if not target_app:
            logger.warning(f"   Could not find app matching '{app_name_query}'")
            return False

        return self.delete_oauth_app_by_url(
            app_url=target_app["url"],
            app_name=target_app["name"],
        )

    def delete_oauth_app_by_url(self, app_url: str, app_name: str) -> bool:
        logger.info(f"🗑️  Deleting OAuth app: {app_name}")
        try:
            self.page.goto(app_url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(1)
            self.handle_sudo_mode()
            time.sleep(1)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)

            clicked = False
            for selector in GitHubSelectors.DELETE_BUTTONS:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                logger.error("   Could not find delete button")
                return False

            confirmation_input = self.page.query_selector(GitHubSelectors.CONFIRM_DELETE_INPUT)
            if confirmation_input and confirmation_input.is_visible():
                confirmation_input.fill(app_name)
                time.sleep(0.5)
                
                for selector in GitHubSelectors.CONFIRM_DELETE_BUTTONS:
                    try:
                        confirm_btn = self.page.query_selector(selector)
                        if confirm_btn and confirm_btn.is_visible():
                            confirm_btn.click()
                            logger.info("   Confirmed deletion")
                            try:
                                self.page.wait_for_url("**/settings/developers", timeout=10000)
                                logger.info("   ✅ App deleted successfully")
                                return True
                            except:
                                return True
                    except Exception:
                        continue
            return False
        except Exception as e:
            logger.error(f"   ❌ Deletion failed: {e}")
            return False

    def create_oauth_app(self, config: OAuthConfig) -> OAuthCredentials:
        logger.info(f"📝 Navigate to create app: {config.name}")
        self.page.goto("https://github.com/settings/applications/new")
        self.handle_sudo_mode()
        self.page.wait_for_selector(GitHubSelectors.APP_NAME_INPUT, timeout=15000)

        while True:
            logger.info("   Filling form details...")
            self.page.fill(GitHubSelectors.APP_NAME_INPUT, config.name)
            self.page.fill(GitHubSelectors.APP_URL_INPUT, config.homepage_url)
            self.page.fill(GitHubSelectors.APP_DESC_INPUT, config.description)
            self.page.fill(GitHubSelectors.CALLBACK_URL_INPUT, config.callback_url)
            
            logger.info("   Submitting form...")
            self.page.click(GitHubSelectors.REGISTER_BUTTON)

            try:
                for _ in range(10):
                    if "/settings/applications/" in self.page.url and "/new" not in self.page.url:
                        break
                    
                    error_el = self.page.query_selector('.flash-error, .error')
                    if error_el and error_el.is_visible():
                        error_text = error_el.inner_text().lower()
                        if "already taken" in error_text:
                            print(f"\n❌ Error: Name '{config.name}' is already taken.")
                            new_name = input("Enter a different app name: ").strip()
                            if new_name:
                                config.name = new_name
                                self.page.fill(GitHubSelectors.APP_NAME_INPUT, "")
                                break
                    time.sleep(0.5)
                else: 
                     if "/settings/applications/" in self.page.url:
                         break
                     pass
                
                if "/settings/applications/" in self.page.url and "/new" not in self.page.url:
                    break
            except Exception:
                break

        app_url = self.page.url
        logger.info("   Extracting Client ID...")
        client_id_node = self.page.wait_for_selector(GitHubSelectors.CLIENT_ID_DISPLAY)
        client_id = client_id_node.inner_text().strip()
        
        logger.info("   Generating Client Secret...")
        self._generate_secret()
        client_secret = self._capture_secret(client_id)

        return OAuthCredentials(
            client_id=client_id,
            client_secret=client_secret,
            app_name=config.name,
            app_url=app_url,
        )

    def _generate_secret(self):
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        
        for selector in GitHubSelectors.GENERATE_SECRET_BUTTONS:
            try:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(1)
                    self.handle_sudo_mode()
                    return
            except Exception:
                continue
        raise Exception("Could not find 'Generate client secret' button")

    def _capture_secret(self, client_id: str) -> str:
        for _ in range(20):
            codes = self.page.query_selector_all("code")
            for code_el in codes:
                text = code_el.inner_text().strip()
                if len(text) > 30 and text != client_id:
                    return text
            time.sleep(0.5)
        
        print("\nCould not auto-capture secret. Please paste it manually:")
        return input("Client Secret: ").strip()
