from typing import Optional


def prompt(text: str, default: str = "") -> str:
    if default:
        result = input(f"\033[94m➤\033[0m {text} \033[90m[{default}]\033[0m: ").strip()
        return result if result else default
    return input(f"\033[94m➤\033[0m {text}: ").strip()


def prompt_yes_no(text: str, default: bool = True) -> bool:
    default_hint = "[Y/n]" if default else "[y/N]"
    result = input(f"\033[94m➤\033[0m {text} {default_hint}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def prompt_choice(text: str, choices: list, default: int = 1) -> int:
    print(f"\n\033[94m➤\033[0m {text}")
    for i, choice in enumerate(choices, 1):
        marker = "●" if i == default else "○"
        print(f"   {marker} {i}. {choice}")
    
    while True:
        result = input(f"   Enter choice (1-{len(choices)}) [{default}]: ").strip()
        if not result:
            return default
        try:
            choice = int(result)
            if 1 <= choice <= len(choices):
                return choice
        except ValueError:
            pass
        print(f"\033[91m   Invalid choice. Please enter 1-{len(choices)}.\033[0m")
