import sys

from ..utils import prompt, prompt_yes_no, select_env_file, write_credentials_to_env, prompt_choice
from ..core import setup_logger
from .config import GoogleOAuthConfig
from .automator import GoogleAutomator

logger = setup_logger("oauth_automator.google.cli")


def interactive_create():
    logger.info("🚀 Starting interactive Google OAuth creation...")
    
    try:
        app_name = prompt("Enter App Name", "My Google App")
        
        # App Type Selection
        types = ["Web application", "Desktop app", "Android", "iOS", "TVs", "Universal Windows Platform"]
        type_idx = prompt_choice("Select Application Type", types, 1)
        # Map index to value expected by config
        # Simplify for now to assume web/desktop common cases or map correctly
        type_map = {1: "WEB", 2: "DESKTOP", 3: "ANDROID", 4: "IOS", 5: "TV_LIMITED_INPUT", 6: "UWP"}
        app_type = type_map.get(type_idx, "WEB")
        
        config = GoogleOAuthConfig(
            name=app_name,
            app_type=app_type
        )
        
        if app_type == "WEB":
            origin = prompt("Javascript Origin", "http://localhost:3000")
            redirect = prompt("Redirect URI", "http://localhost:3000/api/auth/callback/google")
            if origin:
                config.javascript_origins.append(origin)
            if redirect:
                config.redirect_uris.append(redirect)
        
        env_file = select_env_file()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    
    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)
    
    try:
        page = browser_manager.start()
        automator = GoogleAutomator(page)
        
        automator.ensure_logged_in()
        automator.select_or_create_project()
        
        # Determine if we need consent screen (usually once per project, but safe to check)
        # For simplicity in this CLI port, we'll ask or just do it
        if prompt_yes_no("Configure OAuth Consent Screen first?", False):
            automator.setup_consent_screen(config)
            
        credentials = automator.create_oauth_client(config)
        
        logger.info(f"✅ Client '{credentials.app_name}' created successfully!")
        
        if write_credentials_to_env(
            credentials={
                "GOOGLE_CLIENT_ID": credentials.client_id,
                "GOOGLE_CLIENT_SECRET": credentials.client_secret,
                "GOOGLE_PROJECT_ID": credentials.project_id
            },
            env_file=env_file
        ):
            logger.info(f"📝 Credentials saved to {env_file}")
            
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
        automator = GoogleAutomator(page)
        automator.ensure_logged_in()
        automator.select_or_create_project()
        automator.list_oauth_clients()
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
        automator = GoogleAutomator(page)
        automator.ensure_logged_in()
        automator.select_or_create_project()
        
        # Listing first helps user know what to delete
        automator.list_oauth_clients()
        
        client_name = prompt("Enter name of client to delete")
        if not client_name:
            return
            
        automator.delete_oauth_client(client_name)
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
        automator = GoogleAutomator(page)
        automator.ensure_logged_in()
        automator.select_or_create_project()
        run_manager(automator)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    finally:
        browser_manager.close()


def interactive_main():
    while True:
        print("\n\033[1mGoogle OAuth Automator\033[0m")
        print("1. Create new client")
        print("2. List clients")
        print("3. Delete client")
        print("4. Manage clients (interactive)")
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
