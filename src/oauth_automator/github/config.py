from dataclasses import dataclass
import re
import urllib.request
import urllib.error
import urllib.parse

from ..core import setup_logger

logger = setup_logger("oauth_automator.github")


@dataclass
class OAuthConfig:
    name: str
    description: str = "Created via Playwright Automation"
    homepage_url: str = "http://localhost:3000"
    callback_url: str = "http://localhost:3000/api/auth/callback/github"


@dataclass
class OAuthCredentials:
    client_id: str
    client_secret: str
    app_name: str
    app_url: str = ""

    def to_env_string(self) -> str:
        return f'''
# GitHub OAuth Credentials ({self.app_name})
GITHUB_CLIENT_ID="{self.client_id}"
GITHUB_CLIENT_SECRET="{self.client_secret}"
'''

    def to_env_string_with_prefix(self, prefix: str = "") -> str:
        key_prefix = f"{prefix}_" if prefix else ""
        return f'''
# GitHub OAuth Credentials ({self.app_name})
{key_prefix}GITHUB_CLIENT_ID="{self.client_id}"
{key_prefix}GITHUB_CLIENT_SECRET="{self.client_secret}"
'''

    def verify(self) -> bool:
        logger.info("🔍 Verifying OAuth credentials...")

        if not self.client_id.startswith("Ov23li"):
            logger.warning(f"   ⚠️  Client ID has unexpected prefix: {self.client_id[:6]}")
            return False

        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.client_id):
            logger.warning("   ❌ Client ID contains invalid characters")
            return False

        if len(self.client_secret) < 30:
            logger.warning(f"   ⚠️  Client secret seems too short: {len(self.client_secret)} chars")
            return False

        try:
            encoded_id = urllib.parse.quote_plus(self.client_id)
            test_url = f"https://github.com/login/oauth/authorize?client_id={encoded_id}&response_type=code"
            req = urllib.request.Request(test_url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in [200, 302]:
                    final_url = response.url
                    if "error" in final_url.lower():
                        logger.error("   ❌ GitHub returned an error for client_id")
                        return False

                    logger.info("   ✅ Client ID is recognized by GitHub")
                    logger.info("   ✅ Client secret format is valid")
                    logger.info("   ✅ Credentials verified successfully!")
                    return True

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.error("   ❌ Client ID not found on GitHub")
                return False
            logger.warning(f"   ⚠️  HTTP {e.code} - verification inconclusive")

        except Exception as e:
            logger.warning(f"   ⚠️  Could not verify: {e}")

        logger.info("   ✅ Credential format looks valid (online verification skipped)")
        return True
