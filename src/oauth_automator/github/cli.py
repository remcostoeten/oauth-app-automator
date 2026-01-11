import sys

from ..utils import prompt, prompt_yes_no, select_env_file, write_credentials_to_env
from ..core import setup_logger
from .config import OAuthConfig, OAuthCredentials
from .automator import GitHubAutomator

logger = setup_logger("oauth_automator.github.cli")


def interactive_create():
    logger.info("🚀 Starting interactive GitHub OAuth App creation...")
    
    try:
        app_name = prompt("Enter App Name", "My App")
        homepage = prompt("Enter Homepage URL", "http://localhost:3000")
        callback = prompt("Enter Callback URL", "http://localhost:3000/api/auth/callback/github")
        
        env_file = select_env_file()
        
        config = OAuthConfig(
            name=app_name,
            homepage_url=homepage,
            callback_url=callback
        )
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    
    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)
    
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        
        automator.ensure_logged_in()
        credentials = automator.create_oauth_app(config)
        
        logger.info(f"✅ App '{credentials.app_name}' created successfully!")
        logger.info(f"🔑 Client ID: {credentials.client_id}")
        
        if write_credentials_to_env(
            credentials={
                "GITHUB_CLIENT_ID": credentials.client_id,
                "GITHUB_CLIENT_SECRET": credentials.client_secret
            },
            env_file=env_file
        ):
            logger.info(f"📝 Credentials saved to {env_file}")

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
