import time
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

    def list_oauth_apps(self) -> List[dict]:
        logger.info("📋 Fetching OAuth apps list...")
        self.page.goto("https://github.com/settings/developers")
        self.handle_sudo_mode()
        time.sleep(2)

        apps = []
        page_num = 1

        while True:
            logger.info(f"   Scanning page {page_num}...")
            found_on_page = 0
            
            for selector in GitHubSelectors.APP_LINKS:
                app_elements = self.page.query_selector_all(selector)
                for el in app_elements:
                    href = el.get_attribute("href")
                    if not href or "/new" in href or href.endswith("/settings/applications"):
                        continue

                    path_parts = href.split("/")
                    if len(path_parts) >= 4 and path_parts[-1].isdigit():
                        name = el.inner_text().strip()
                        if name:
                            app_url = f"https://github.com{href}" if href.startswith("/") else href
                            if not any(app["url"] == app_url for app in apps):
                                apps.append({"name": name, "url": app_url})
                                found_on_page += 1

            logger.info(f"   Found {found_on_page} apps on page {page_num}")

            next_btn = self.page.query_selector(GitHubSelectors.NEXT_PAGE_LINK)
            if next_btn and next_btn.is_visible():
                next_btn.click()
                time.sleep(1.5)
                page_num += 1
            else:
                break

        logger.info(f"   Total found: {len(apps)} OAuth app(s)")
        print(f"\nFound {len(apps)} apps:")
        for i, app in enumerate(apps, 1):
            print(f"{i}. {app['name']} ({app['url']})")
        return apps

    def delete_oauth_app(self, app_name_query: str) -> bool:
        apps = self.list_oauth_apps()
        target_app = next((a for a in apps if app_name_query.lower() in a["name"].lower()), None)
        
        if not target_app:
            logger.warning(f"   Could not find app matching '{app_name_query}'")
            return False
            
        logger.info(f"🗑️  Deleting OAuth app: {target_app['name']}")
        try:
            self.page.goto(target_app["url"], timeout=20000, wait_until="domcontentloaded")
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
                confirmation_input.fill(target_app["name"])
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
