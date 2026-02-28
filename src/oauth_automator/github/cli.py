import sys
from typing import Optional

from ..utils import prompt, prompt_choice, prompt_yes_no, select_env_file, write_credentials_to_env
from ..utils.clipboard import copy_to_clipboard
from ..core import setup_logger
from .config import OAuthConfig, OAuthCredentials
from .automator import GitHubAutomator

logger = setup_logger("oauth_automator.github.cli")


def _format_create_clipboard(client_id: str, client_secret: str, use_comma: bool) -> str:
    if use_comma:
        return f"{client_id},{client_secret}"
    return f"GITHUB_CLIENT_ID={client_id}\nGITHUB_CLIENT_SECRET={client_secret}"


def _select_app(apps: list, app_id: Optional[str], app_name: Optional[str]) -> Optional[dict]:
    if app_id:
        return next((app for app in apps if str(app.get("id", "")) == str(app_id)), None)

    if app_name:
        exact = [app for app in apps if app["name"].lower() == app_name.lower()]
        if exact:
            return exact[0]
        partial = [app for app in apps if app_name.lower() in app["name"].lower()]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            print("\nMultiple apps matched by name:")
            for i, app in enumerate(partial, 1):
                print(f"{i}. [{app.get('id', 'unknown')}] {app['name']}")
            idx_raw = prompt("Choose app number", "1")
            try:
                idx = int(idx_raw)
                if 1 <= idx <= len(partial):
                    return partial[idx - 1]
            except ValueError:
                pass
            return None
        return None

    if not apps:
        return None

    print("\nSelect an app:")
    for i, app in enumerate(apps, 1):
        print(f"{i}. [{app.get('id', 'unknown')}] {app['name']}")

    while True:
        idx_raw = prompt("Choose app number", "1")
        try:
            idx = int(idx_raw)
            if 1 <= idx <= len(apps):
                return apps[idx - 1]
        except ValueError:
            pass
        print("Invalid choice")


def _format_credentials(client_id: str, client_secret: str, output_format: str, prefix: str) -> str:
    if output_format == "public":
        return client_id
    if output_format == "secret":
        return client_secret
    if output_format == "both-comma":
        return f"{client_id},{client_secret}"
    if output_format == "both-lines":
        return f"{client_id}\n{client_secret}"

    key_prefix = prefix.upper()
    return (
        f"{key_prefix}GITHUB_CLIENT_ID={client_id}\n"
        f"{key_prefix}GITHUB_CLIENT_SECRET={client_secret}"
    )


def _secret_from_audit_history(client_id: str, app_name: str) -> str:
    try:
        from .audit import AuditLogger
        audit = AuditLogger()
        entries = audit.read_log()
        if not entries:
            return ""

        # Prefer exact client_id match, fallback to latest app_name match.
        for entry in reversed(entries):
            if entry.get("client_id") == client_id and entry.get("client_secret"):
                return entry["client_secret"]

        for entry in reversed(entries):
            if entry.get("app_name", "").lower() == app_name.lower() and entry.get("client_secret"):
                return entry["client_secret"]
    except Exception:
        return ""
    return ""


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
        for key, value in all_credentials.items():
            print(f"{key}={value}")
        print("=" * 50)

        # Optionally copy local credentials in a paste-friendly format
        if prompt_yes_no("Copy local credentials to clipboard?", default=True):
            format_choice = prompt_choice(
                "Choose clipboard format:",
                [
                    "Comma-separated (client_id,client_secret)",
                    "Env lines (GITHUB_CLIENT_ID=... and GITHUB_CLIENT_SECRET=...)",
                ],
                default=2,
            )
            use_comma = format_choice == 1
            clipboard_text = _format_create_clipboard(
                credentials.client_id,
                credentials.client_secret,
                use_comma,
            )
            if copy_to_clipboard(clipboard_text):
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


def interactive_list(args=None):
    from ..core.browser import BrowserManager
    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()
        refresh = bool(getattr(args, "refresh", False))
        automator.list_oauth_apps(refresh=refresh)
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


def interactive_grab(args):
    from ..core.browser import BrowserManager

    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()

        arg_id = getattr(args, "id", None)
        arg_name = getattr(args, "name", None)
        refresh = bool(getattr(args, "refresh", False))

        if arg_id:
            target_app = {
                "id": str(arg_id),
                "name": arg_name or f"OAuth App {arg_id}",
                "url": f"https://github.com/settings/applications/{arg_id}",
            }
        elif arg_name:
            matched_apps = automator.find_oauth_apps_by_name(arg_name, refresh=refresh)
            if len(matched_apps) == 1:
                target_app = matched_apps[0]
            elif len(matched_apps) > 1:
                target_app = _select_app(matched_apps, None, arg_name)
            else:
                target_app = None
        else:
            apps = automator.list_oauth_apps(refresh=refresh)
            target_app = _select_app(apps, None, None)

        if not target_app:
            logger.warning("⚠️ No matching OAuth app found.")
            return

        output_format = getattr(args, "format", "env-lines")
        allow_public_fallback = bool(getattr(args, "allow_public_fallback", True))
        needs_secret = output_format in {"secret", "both-comma", "both-lines", "env-lines"}
        credentials = automator.grab_oauth_credentials(
            app_url=target_app["url"],
            app_name=target_app["name"],
            generate_secret_if_missing=False,
        )

        if needs_secret and not credentials.client_secret:
            recovered = _secret_from_audit_history(credentials.client_id, credentials.app_name)
            if recovered:
                credentials.client_secret = recovered
                logger.info("🔓 Recovered client secret from secure local history.")

        if needs_secret and not credentials.client_secret:
            if prompt_yes_no("Client secret not visible. Generate a NEW client secret now?", default=False):
                credentials = automator.grab_oauth_credentials(
                    app_url=target_app["url"],
                    app_name=target_app["name"],
                    generate_secret_if_missing=True,
                )

        if needs_secret and not credentials.client_secret:
            if allow_public_fallback:
                logger.warning("⚠️ Client secret unavailable. Falling back to public client ID only.")
                output_format = "public"
            else:
                logger.error("❌ Client secret could not be captured.")
                return

        prefix = getattr(args, "prefix", "GIT_")
        formatted = _format_credentials(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            output_format=output_format,
            prefix=prefix,
        )

        print("\n" + "=" * 50)
        print("\033[1m📋 Grabbed OAuth Credentials:\033[0m")
        print("=" * 50)
        print(formatted)
        print("=" * 50)

        if copy_to_clipboard(formatted):
            logger.info("📋 Copied to clipboard.")
        else:
            logger.warning("⚠️ Could not copy to clipboard.")
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        return
    finally:
        browser_manager.close()


def interactive_cleanup(args=None):
    from ..core.browser import BrowserManager

    browser_manager = BrowserManager(headless=False)
    try:
        page = browser_manager.start()
        automator = GitHubAutomator(page)
        automator.ensure_logged_in()

        refresh = bool(getattr(args, "refresh", False))
        apps = automator.list_oauth_apps(refresh=refresh)
        if not apps:
            logger.info("No apps found.")
            return

        logger.info("🧪 Inspecting app usage and creation date (this can take a while)...")
        report = automator.inspect_all_oauth_apps_usage(apps)

        unused = [app for app in report if app.get("is_unused") is True]
        unknown = [app for app in report if app.get("usage_known") is False]
        used = [app for app in report if app.get("authorized_users", 0) > 0]

        print("\n" + "=" * 70)
        print("\033[1mOAuth Cleanup Report\033[0m")
        print("=" * 70)
        print(f"Total: {len(report)} | Used: {len(used)} | Unused: {len(unused)} | Unknown: {len(unknown)}")

        if unused:
            print("\nUnused apps (authorized users = 0):")
            for i, app in enumerate(unused, 1):
                print(
                    f"{i}. [{app.get('id', 'unknown')}] {app['name']} | "
                    f"created: {app.get('created_at', 'unknown')}"
                )
        else:
            print("\nNo confidently unused apps found.")

        if unknown:
            print("\nUsage unknown (not auto-deleted):")
            for app in unknown[:15]:
                print(
                    f"- [{app.get('id', 'unknown')}] {app['name']} | "
                    f"created: {app.get('created_at', 'unknown')}"
                )
            if len(unknown) > 15:
                print(f"... and {len(unknown) - 15} more")

        if not unused:
            return

        print("\nActions:")
        print("1. Delete one unused app")
        print("2. Delete ALL unused apps")
        print("3. Cancel")
        action = prompt("Choose action", "3")

        if action == "1":
            choice_raw = prompt("Unused app number to delete")
            try:
                choice = int(choice_raw)
                if 1 <= choice <= len(unused):
                    app = unused[choice - 1]
                    automator.delete_oauth_app_by_url(app["url"], app["name"])
                else:
                    print("Invalid number")
            except ValueError:
                print("Invalid number")
        elif action == "2":
            if prompt_yes_no(f"Delete {len(unused)} unused apps now?", default=False):
                deleted = 0
                for app in unused:
                    if automator.delete_oauth_app_by_url(app["url"], app["name"]):
                        deleted += 1
                logger.info(f"✅ Deleted {deleted}/{len(unused)} unused apps.")
        else:
            print("Cancelled")
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
        print("5. Grab credentials to clipboard")
        print("6. Cleanup unused apps")
        print("7. Back to main menu")
        
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
            class _Args:
                id = None
                name = None
                format = "env-lines"
                prefix = "GIT_"
                allow_public_fallback = True
            interactive_grab(_Args())
        elif choice == "6":
            interactive_cleanup()
        elif choice == "7":
            return
        else:
            print("Invalid choice")


def handle_command(args):
    if args.command == "create":
        interactive_create()
    elif args.command == "list":
        interactive_list(args)
    elif args.command == "delete":
        interactive_delete()
    elif args.command == "manage":
        interactive_manage()
    elif args.command == "grab":
        interactive_grab(args)
    elif args.command == "cleanup":
        interactive_cleanup(args)
    else:
        interactive_main()
