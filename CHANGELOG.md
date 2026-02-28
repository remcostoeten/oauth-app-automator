```
# Changelog

All notable changes to this project will be documented in this file.

## [1.4.1] - 2026-02-28

### Improvements
- **Faster OAuth App Usage Inspection**:
    - Added parallel GitHub OAuth app usage inspection using authenticated HTTP requests for significantly faster list scans.
    - Added automatic fallback to Playwright-based inspection for apps that require re-auth/sudo or fail HTTP inspection.
- **Smarter `run.sh` Bootstrap**:
    - `run.sh` now ensures `.venv` exists automatically (prefers `uv venv`, falls back to `python -m venv`).
    - Added dependency hash tracking so installs only run when `requirements.txt` changes.
    - Uses `uv pip` when available, with automatic fallback to standard `pip`.

## [1.4.0] - 2026-01-07

### New Features
- **Global Installation**: 
    - Added `pyproject.toml` for proper Python packaging
    - Created `install.sh` script for one-command global installation via `uv tool install`
    - New CLI commands: `create-github-oauth` and `create-google-oauth` work from any directory
    - Updated README with installation options (local vs global usage)

### Bug Fixes
- **Dynamic Callback URLs**: Fixed issue where callback URL would stay on default port (3000) even when homepage URL was changed
    - Callback URL now correctly derives from the user-provided homepage URL in real-time
- **README Media**: Converted demo video to optimized GIF (2.5MB) for proper GitHub display

### Improvements
- Fixed syntax error in shebang line

---

## [1.3.0] - 2026-01-06

### Secure Audit Logging
- **Encrypted Local History**: 
    - Automatically logs all generated credentials (Client ID, Secret, App Name) to an encrypted local file (`~/.oauth-automator/github/history.enc`).
    - Uses **Fernet (AES-128)** encryption with a strictly permissioned key file (`~/.oauth-automator/.key` mode 600).
    - **Opt-In**: Enabled via `setup.sh` prompt or Menu Option 7.
- **Audit Viewer**: Interactive CLI to view logged history and selectively decrypt/reveal secrets.

### Reliability & Edge Cases
- **Duplicate App Name Protection**: 
    - Detects if GitHub rejects an app name ("Name is already taken").
    - Interactively prompts for a new name and auto-retries submission without crashing.
- **Smart Setup**:
    - `setup.sh` now detects existing `uv` and Playwright installations to skip redundant downloads (~30s saved).
    - Checks for system browsers (Brave/Chrome) to avoid unnecessary Playwright binary installs.

### Features
- **Dual Environment Creation**: Generate DEV and PROD apps simultaneously.
- **Split Configuration**: Save DEV credentials to `.env.local` and PROD to `.env.production`.
- **Smart Env Handling**: Auto-archives old keys (`# OLD_GITHUB_...`) instead of overwriting.
- **Clipboard Sync**: Auto-copies credentials to system clipboard (xclip/pbcopy).

### Bug Fixes
- **Deletion Hang**: Fixed an issue where the script would freeze during app deletion due to strict network idle checks (switched to `domcontentloaded`).
- **URL Sanitization**: Automatically strips trailing slashes from homepage URLs.

---

## [0.1.0] - Initial MVP

### Added
- **Automated OAuth Creation**: Uses Playwright to automate the GitHub OAuth application creation form.
- **Credential Extraction**: Scrapes Client ID and generates Client Secret automatically.
- **Environment Management**: Writes `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` to a local `.env` file.
- **Sudo Mode Handling**: Detects GitHub's password confirmation prompts and handles them interactively.
- **Browser Session Management**: Reuses browser profile to avoid 2FA/login repetition.
- **Basic Verification**: Interactive script to verify generated credentials against the GitHub API.
- **App Deletion**: Utility to delete existing OAuth apps.
```
