# OAuth App Automator

Create GitHub and Google OAuth apps in seconds.

This tool automates the painful manual setup flow for GitHub OAuth apps and Google OAuth clients. It generates client IDs and secrets for you, then copies them to your clipboard or writes them directly to your `.env` files so you can get back to building.

It is built for local development, staging, and production setup without spending half your day clicking through GitHub settings and Google Cloud Console.

If you want to understand the browser automation approach and security model, read [How it works](#how-it-works).

![Demo](DEMO.gif)

## Quick Start

### Option A: Local Usage

**1. Setup (first time only)**  
Run the interactive setup script to configure dependencies and settings:

```bash
./setup.sh
```

_The setup script verifies Python, installs dependencies, and can help you connect an existing Brave or Chrome profile if you want to reuse a logged-in browser session._

**2. Run**

Create a GitHub OAuth app:
```bash
./run.sh
```

Create a Google OAuth client:
```bash
python google_oauth_automator.py
```

---

### Option B: Global Installation

Install globally with shell aliases:

```bash
./install-cli.sh
```

Then run from anywhere:
```bash
create-oauth           # GitHub OAuth (shortcut)
create-github-oauth   # GitHub OAuth
create-google-oauth   # Google OAuth
```

The installer detects your shell and writes a small sourced snippet instead of relying on a brittle alias setup.

- `bash`: writes `~/.config/oauth-creator/oauth-creator.bash`
- `zsh` / `sh`: writes `~/.config/oauth-creator/oauth-creator.sh`
- `fish`: writes `~/.config/oauth-creator/oauth-creator.fish`
- Unknown shell setup: still writes a snippet and prints the exact line to source from your own shell config

In standard setups it will also add the matching `source` line to your shell config automatically. If that is not safe for your setup, the installer prints the snippet path and the exact command to run manually.

### Update

To update to the latest version, pull the changes and run install again:

```bash
git pull
./install-cli.sh
```

---

Both flows prompt for the values they need and can save generated credentials directly to `.env`.

## Features

- Create GitHub OAuth apps automatically
- Create Google OAuth clients automatically
- Generate client secrets without manual setup
- Create DEV and PROD GitHub apps in one run
- Set up the Google consent screen as part of the flow
- Select or create a Google Cloud project
- Support Web and Desktop Google OAuth client types
- Copy generated credentials to the clipboard
- Write credentials to `.env`, `.env.local`, or `.env.production`
- Avoid overwriting existing environment variables with smart `GENERATED_` prefixes
- Navigate interactive menus with arrow keys or number keys
- Delete existing GitHub OAuth apps through the GitHub API

## How it works

GitHub and Google do not provide a clean modern API for every OAuth app creation flow. This tool uses browser automation to handle the same steps you would normally do by hand:

1. Opens a browser (headless or visible).  
2. Navigates to the required GitHub or Google setup pages.  
3. Fills out the form with your config.  
4. Generates a client secret.  
5. Copies the credentials to your clipboard or saves them to your `.env` file.  

## Configuration

The `./setup.sh` script will create a `.env` file for you. For GitHub:

`setup.sh` and the interactive GitHub flow now offer `Next.js (3000)`, `Vite (5173)`, `custom localhost port`, or `full custom URL` modes, then derive the callback URL from that choice.

```ini
OAUTH_APP_NAME="My App"
GITHUB_PASSWORD="your-password"             # Optional - for auto-filling Sudo Mode
OAUTH_BASE_URL="http://localhost:3000"
OAUTH_CALLBACK_URL="http://localhost:3000/api/auth/callback/github"
OAUTH_PROD_BASE_URL="https://your-production-domain.com"  # For DEV+PROD mode
OAUTH_PROD_CALLBACK_URL="https://your-production-domain.com/api/auth/callback/github"
PLAYWRIGHT_SLOW_MO="0"                      # Optional - set >0 to slow browser actions for debugging
```

For Google:

```ini
GOOGLE_OAUTH_APP_NAME="My Google App"
GOOGLE_PROJECT_ID="your-google-cloud-project-id"
OAUTH_BASE_URL="http://localhost:3000"
OAUTH_CALLBACK_URL="http://localhost:3000/api/auth/callback/google"
BROWSER_PROFILE_PATH="/home/user/.config/BraveSoftware/Brave-Browser/Default" # Optional
```

If for some reason it fails, you can just copy `.env.example` and fill the credentials in there.

### Duplicate Key Handling

When writing credentials to an existing `.env` file, the script will **never overwrite** existing keys. Instead:

1. If `GITHUB_CLIENT_ID` already exists, new credentials are saved as `GENERATED_GITHUB_CLIENT_ID`
2. If that also exists, it becomes `GENERATED_2_GITHUB_CLIENT_ID`, and so on

⚠️ **Important:** You'll need to manually update your application to use the new keys, or replace the old values.

## Troubleshooting

- **“Browser already running”**: If you use a custom Brave or Chrome profile, you must close the browser before running the script. Playwright cannot attach to a running browser instance.  
- **“Executable doesn't exist” / missing Playwright Chromium**: The script now tries to recover automatically by running `npm i -g playwright` when needed and then `playwright install chromium`. If that automatic recovery fails, run those commands manually and retry.  
- **Sudo mode**: When accessing sensitive settings, GitHub asks for your password. 
  - To **avoid manual entry**: Add `GITHUB_PASSWORD="your-password"` to your `.env` file. The script will auto-fill it.
  - Otherwise, the script will ask you to enter it in the terminal once per session.  
- **Anything else**: Re-run with a visible browser, check the prompts carefully, and inspect your `.env` output before retrying.

---

## Why this exists

Creating OAuth apps should take seconds, not a full trip through settings pages and Google Cloud Console. This project exists to remove that setup tax.
