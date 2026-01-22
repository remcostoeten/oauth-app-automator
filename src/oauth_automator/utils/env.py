import os
from pathlib import Path
from typing import Optional


def select_env_file() -> str:
    print("\n\033[94m➤\033[0m Select environment file:")
    files = [".env", ".env.local", ".env.production", "Custom path..."]
    
    for i, f in enumerate(files, 1):
        print(f"   {i}. {f}")
    
    while True:
        choice = input("   Enter choice (1-4) [1]: ").strip()
        if not choice:
            return ".env"
        try:
            idx = int(choice)
            if idx == 4:
                return input("   Enter custom path: ").strip()
            if 1 <= idx <= 3:
                return files[idx - 1]
        except ValueError:
            pass
        print("\033[91m   Invalid choice.\033[0m")


def write_credentials_to_env(
    credentials: dict,
    env_file: str = ".env",
    prefix: str = ""
) -> bool:
    try:
        env_path = Path(env_file)
        existing_content = ""
        existing_keys = set()
        
        if env_path.exists():
            existing_content = env_path.read_text()
            for line in existing_content.split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=")[0].strip()
                    existing_keys.add(key)
        
        new_lines = []
        for key, value in credentials.items():
            full_key = f"{prefix}{key}" if prefix else key
            
            if full_key in existing_keys:
                counter = 1
                candidate = f"GENERATED_{counter}_{full_key}"
                while candidate in existing_keys:
                    counter += 1
                    candidate = f"GENERATED_{counter}_{full_key}"
                full_key = candidate
            
            new_lines.append(f'{full_key}="{value}"')
        
        with open(env_path, "a") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(new_lines) + "\n")
        
        return True
    except Exception:
        return False
