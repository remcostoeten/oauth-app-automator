import urllib.request
import urllib.error
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

REPO_OWNER = "remcostoeten"
REPO_NAME = "automatic-oauth-github-creator"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
except ImportError:
    # Fallback if neither is available (though recent python versions include tomllib)
    def parse_toml_version(path):
        with open(path, "r") as f:
            for line in f:
                if line.strip().startswith("version ="):
                    return line.split("=")[1].strip().strip('"').strip("'")
        return "0.0.0"

def get_current_version() -> str:
    try:
        # Adjusted path since this file is now in src/oauth_automator/core/
        # Root is 3 directories up from core (core -> oauth_automator -> src -> root)
        try:
            # Try to resolve from root
            pyproject_path = Path(__file__).parents[3] / "pyproject.toml"
        except IndexError:
             # Fallback if path structure is not as expected
             pyproject_path = Path(__file__).parent / "pyproject.toml"

        if not pyproject_path.exists():
            return "0.0.0"
            
        with open(pyproject_path, "rb") as f:
            # Try appropriate TOML parser
            try:
                if 'tomllib' in sys.modules or 'tomli' in sys.modules:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "0.0.0")
            except:
                pass
                
        # Simple fallback parsing if Import failed or load failed
        with open(pyproject_path, "r") as f:
            for line in f:
                if line.strip().startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "0.0.0"

CURRENT_VERSION = get_current_version()


def parse_version(version_str: str) -> Tuple[int, ...]:
    clean = version_str.lstrip("v").strip()
    parts = clean.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def fetch_latest_version() -> Optional[str]:
    try:
        req = urllib.request.Request(GITHUB_API_URL)
        req.add_header("User-Agent", "OAuth-Automator-Version-Check")
        req.add_header("Accept", "application/vnd.github.v3+json")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("tag_name", "").lstrip("v")
    except Exception:
        return None


def is_update_available() -> Tuple[bool, Optional[str]]:
    latest = fetch_latest_version()
    if not latest:
        return False, None
    
    try:
        current_tuple = parse_version(CURRENT_VERSION)
        latest_tuple = parse_version(latest)
        
        if latest_tuple > current_tuple:
            return True, latest
    except:
        pass
    
    return False, latest


def print_update_notice():
    update_available, latest_version = is_update_available()
    
    if update_available:
        notice = f"""
\033[33m┌──────────────────────────────────────────────────────┐
│  ⚡ Update available: v{CURRENT_VERSION} → v{latest_version:<24} │
│                                                      │
│  Run: \033[1mgit pull\033[0m\033[33m or \033[1mpip install --upgrade .\033[0m\033[33m           │
└──────────────────────────────────────────────────────┘\033[0m
"""
        print(notice)
        return True
    return False


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists() and (path / ".git").is_dir()

def find_repo_root(path: Path) -> Path:
    for candidate in [path] + list(path.parents):
        if is_git_repo(candidate):
            return candidate
    return path

def check_and_update() -> bool:
    update_available, latest_version = is_update_available()
    
    if not update_available:
        print(f"\033[92m✓\033[0m You're on the latest version (v{CURRENT_VERSION})")
        return False
    
    print(f"\n\033[33m⚡ Update available: v{CURRENT_VERSION} → v{latest_version}\033[0m\n")
    
    repo_dir = find_repo_root(Path(__file__).resolve())
    is_git = is_git_repo(repo_dir)
    
    # If not a git repo, we might be installed in site-packages
    if not is_git:
        print(f"\033[93mIt looks like you installed this package via pip or downloaded it directly.\033[0m")
        print(f"To update, please run the following command in your terminal:\n")
        print(f"   \033[1mpip install --upgrade git+https://github.com/{REPO_OWNER}/{REPO_NAME}.git\033[0m")
        print(f"\nOr `git pull` if you are in the cloned directory.")
        input("\nPress Enter to continue...")
        return False

    try:
        choice = input("\033[94m➤\033[0m Would you like to update now? [y/N]: ").strip().lower()
        
        if choice in ("y", "yes"):
            print("\n\033[90mUpdates can cause conflicts if you have local changes.\033[0m")
            print("\033[90mStashing local changes before pulling...\033[0m")
            
            # Stash changes to avoid conflicts (safest simple strategy)
            subprocess.run(["git", "stash"], cwd=repo_dir, capture_output=True)
            
            print("\033[90mPulling latest changes...\033[0m")
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=repo_dir,
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                print(f"\033[92m✓\033[0m Updated to v{latest_version}")
                
                # Check if requirements changed
                try:
                    diff = subprocess.run(
                        ["git", "diff", "HEAD@{1}", "HEAD", "--name-only"], 
                        cwd=repo_dir, capture_output=True, text=True
                    )
                    if "requirements.txt" in diff.stdout:
                         print("\n\033[33m⚠️  Dependencies have changed.\033[0m")
                         print("   Please run: \033[1m./setup.sh\033[0m or \033[1mpip install -r requirements.txt\033[0m")
                except:
                    pass
                
                print("\n\033[90mPlease restart the script to apply changes.\033[0m")
                return True
            else:
                print(f"\033[31m✗\033[0m Update failed: {result.stderr}")
                print("\033[90mRestoring local changes...\033[0m")
                subprocess.run(["git", "stash", "pop"], cwd=repo_dir, capture_output=True)
                print("\033[90mPlease update manually: git pull\033[0m")
                return False
    except KeyboardInterrupt:
        print("\n\033[90mUpdate cancelled.\033[0m")
    
    return False


if __name__ == "__main__":
    print(f"Current version: {CURRENT_VERSION}")
    update_available, latest = is_update_available()
    if latest:
        print(f"Latest version:  {latest}")
        print(f"Update available: {update_available}")
    else:
        print("Could not fetch latest version (offline or rate limited)")
