import sys

from ..utils import prompt, prompt_yes_no, select_env_file, write_credentials_to_env
from ..utils.clipboard import copy_to_clipboard
from ..core import setup_logger
from .config import OAuthConfig, OAuthCredentials
from .automator import GitHubAutomator

logger = setup_logger("oauth_automator.github.cli")


def interactive_create():
    logger.info("🚀 Starting interactive GitHub OAuth App creation...")

    try:
        app_name = prompt("Enter App Name", "My App")
        port = prompt("Enter local development port", "3000")
        homepage = f"http://localhost:{port}"
        callback = f"http://localhost:{port}/api/auth/callback/github"
        logger.info(f"📍 Homepage URL: {homepage}")
        logger.info(f"🔗 Callback URL: {callback}")

        # Ask about production app
        create_prod = prompt_yes_no("Also create production OAuth app?", default=False)
        prod_url = None
        if create_prod:
            prod_url = prompt("Enter production URL (e.g., https://myapp.com)")
            # Strip trailing slash if present
            prod_url = prod_url.rstrip("/")
            prod_homepage = prod_url
            prod_callback = f"{prod_url}/api/auth/callback/github"
            logger.info(f"🌐 Production Homepage: {prod_homepage}")
            logger.info(f"🔗 Production Callback: {prod_callback}")

        env_file = select_env_file()

        config = OAuthConfig(
            name=app_name,
            homepage_url=homepage,
            callback_url=callback
        )

        prod_config = None
        if create_prod and prod_url:
            prod_config = OAuthConfig(
                name=f"{app_name} (Production)",
                homepage_url=prod_homepage,
                callback_url=prod_callback
            )
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return

    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)

    all_credentials = {}

    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)

        automator.ensure_logged_in()

        # Create local dev app
        credentials = automator.create_oauth_app(config)
        logger.info(f"✅ App '{credentials.app_name}' created successfully!")
        logger.info(f"🔑 Client ID: {credentials.client_id}")

        all_credentials["GITHUB_CLIENT_ID"] = credentials.client_id
        all_credentials["GITHUB_CLIENT_SECRET"] = credentials.client_secret

        # Create production app if requested
        prod_credentials = None
        if prod_config:
            prod_credentials = automator.create_oauth_app(prod_config)
            logger.info(f"✅ Production app '{prod_credentials.app_name}' created successfully!")
            logger.info(f"🔑 Production Client ID: {prod_credentials.client_id}")

            all_credentials["PROD_GITHUB_CLIENT_ID"] = prod_credentials.client_id
            all_credentials["PROD_GITHUB_CLIENT_SECRET"] = prod_credentials.client_secret

        # Write all credentials to env file
        if write_credentials_to_env(credentials=all_credentials, env_file=env_file):
            logger.info(f"📝 Credentials saved to {env_file}")

        # Output credentials to CLI
        print("\n" + "=" * 50)
        print("\033[1m📋 Your OAuth Credentials:\033[0m")
        print("=" * 50)
        clipboard_text = ""
        for key, value in all_credentials.items():
            print(f"{key}={value}")
            clipboard_text += f"{key}={value}\n"
        print("=" * 50)

        # Copy to clipboard
        if copy_to_clipboard(clipboard_text.strip()):
            logger.info("📋 Credentials copied to clipboard!")
        else:
            logger.warning("⚠️ Could not copy to clipboard")

        # Secure Audit Logging
        import os
        if os.getenv("ENABLE_SECURE_LOGGING", "").lower() == "true":
            from .audit import AuditLogger
            audit = AuditLogger()
            audit.log_credential(
                app_name=credentials.app_name,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                homepage=config.homepage_url
            )
            if prod_credentials:
                audit.log_credential(
                    app_name=prod_credentials.app_name,
                    client_id=prod_credentials.client_id,
                    client_secret=prod_credentials.client_secret,
                    homepage=prod_config.homepage_url
                )
            logger.info("🔒 Credentials securely logged locally.")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
    finally:
        browser_manager.close()


def interactive_list():
    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()
        automator.list_oauth_apps()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    finally:
        browser_manager.close()


def interactive_delete():
    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()
        
        app_name = prompt("Enter name of OAuth app to delete")
        if not app_name:
            return
            
        automator.delete_oauth_app(app_name)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    finally:
        browser_manager.close()


def interactive_manage():
    from ..core.browser import BrowserManager
    from .manager import interactive_manage as run_manager

    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()
        run_manager(automator)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    finally:
        browser_manager.close()


def interactive_main():
    while True:
        print("\n\033[1mGitHub OAuth Automator\033[0m")
        print("1. Create new app")
        print("2. List apps")
        print("3. Delete app")
        print("4. Manage apps (interactive)")
        print("5. Back to main menu")
        
        choice = input("\n\033[94m➤\033[0m Enter choice: ").strip()
        
        if choice == "1":
            interactive_create()
        elif choice == "2":
            interactive_list()
        elif choice == "3":
            interactive_delete()
        elif choice == "4":
            interactive_manage()
        elif choice == "5":
            return
        else:
            print("Invalid choice")


def handle_command(args):
    if args.command == "create":
        interactive_create()
    elif args.command == "list":
        interactive_list()
    elif args.command == "delete":
        interactive_delete()
    elif args.command == "manage":
        interactive_manage()
    else:
        interactive_main()
