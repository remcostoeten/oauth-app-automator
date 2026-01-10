#!/usr/bin/env python3
import sys
import argparse

from .core.version import CURRENT_VERSION, print_update_notice, check_and_update


def print_banner():
    banner = f"""
\033[38;5;39m
   ██████╗  █████╗ ██╗   ██╗████████╗██╗  ██╗
  ██╔═══██╗██╔══██╗██║   ██║╚══██╔══╝██║  ██║
  ██║   ██║███████║██║   ██║   ██║   ███████║
  ██║   ██║██╔══██║██║   ██║   ██║   ██╔══██║
  ╚██████╔╝██║  ██║╚██████╔╝   ██║   ██║  ██║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝
\033[0m
  \033[1m🔐 OAuth Automator\033[0m \033[90mv{CURRENT_VERSION}\033[0m
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
  \033[36mAutomate OAuth client creation for GitHub & Google\033[0m
  
  \033[90mBy @remcostoeten • github.com/remcostoeten\033[0m
"""
    print(banner)


def print_main_menu():
    menu = """
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
  
  \033[1mSelect a provider:\033[0m
  
    \033[38;5;39m❯\033[0m \033[1m1\033[0m  GitHub OAuth
    \033[38;5;39m❯\033[0m \033[1m2\033[0m  Google OAuth
    \033[38;5;39m❯\033[0m \033[1m3\033[0m  Check for updates
    \033[38;5;39m❯\033[0m \033[1m4\033[0m  Exit
  
  \033[90m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m
"""
    print(menu)


def interactive_mode():
    print_banner()
    print_update_notice()
    
    while True:
        print_main_menu()
        choice = input("\033[94m➤\033[0m Enter choice (1-4): ").strip()
        
        if choice == "1":
            from .github.cli import interactive_main as github_interactive
            github_interactive()
        elif choice == "2":
            from .google.cli import interactive_main as google_interactive
            google_interactive()
        elif choice == "3":
            check_and_update()
        elif choice == "4":
            print("\n\033[96mGoodbye! 👋\033[0m\n")
            break
        else:
            print("\033[91mInvalid choice. Please enter 1-4.\033[0m")


def main():
    if len(sys.argv) == 1:
        interactive_mode()
        return
    
    parser = argparse.ArgumentParser(
        prog="oauth-automator",
        description="Automate OAuth client creation for GitHub & Google",
    )
    parser.add_argument("--version", action="version", version=f"oauth-automator v{CURRENT_VERSION}")
    
    subparsers = parser.add_subparsers(dest="provider", help="OAuth provider")
    
    github_parser = subparsers.add_parser("github", help="GitHub OAuth commands")
    github_sub = github_parser.add_subparsers(dest="command")
    github_sub.add_parser("create", help="Create new OAuth app")
    github_sub.add_parser("list", help="List OAuth apps")
    github_sub.add_parser("delete", help="Delete OAuth app")
    
    google_parser = subparsers.add_parser("google", help="Google OAuth commands")
    google_sub = google_parser.add_subparsers(dest="command")
    google_sub.add_parser("create", help="Create new OAuth client")
    google_sub.add_parser("list", help="List OAuth clients")
    google_sub.add_parser("delete", help="Delete OAuth client")
    
    args = parser.parse_args()
    
    if args.provider == "github":
        from .github import cli as github_cli
        github_cli.handle_command(args)
    elif args.provider == "google":
        from .google import cli as google_cli
        google_cli.handle_command(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n\033[93m👋 Operation cancelled by user. Exiting...\033[0m")
        sys.exit(0)
