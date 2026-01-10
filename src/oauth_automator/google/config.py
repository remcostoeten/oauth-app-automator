from dataclasses import dataclass, field
from typing import List, Optional

from ..core import setup_logger

logger = setup_logger("oauth_automator.google")


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
            "",
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
            "",
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

        logger.info("   ✅ Client ID format is valid")
        logger.info("   ✅ Client secret format is valid")
        logger.info("   ✅ Credentials verified successfully!")
        return True
