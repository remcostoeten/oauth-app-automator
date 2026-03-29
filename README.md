# OAuth Automator (GitHub + Google)

For people who value their time<br>
<small>I obviously don't, as I've written this tool</small>

This tool automates the tedious process of creating OAuth applications for both GitHub and Google, since both platforms have deprecated API endpoints for creating new OAuth apps.

If you’re concerned about security, read how this tool [works](#how-it-works).

![Demo](DEMO.gif)

## Quick Start

### Option A: Local Usage (Recommended for First-Time Users)

**1. Setup (first time only)**  
Run the interactive setup script to configure dependencies and settings:

```bash
./setup.sh
```

_It will verify Python, install dependencies (using `uv` for speed), and help you link your existing Brave or Chrome session (optional)._

**2. Run**

For GitHub OAuth:
```bash
./run.sh
```

For Google OAuth:
```bash
python google_oauth_automator.py
```

---

### Option B: Global Installation (Use From Anywhere)

Install globally to use simple commands from any directory:

```bash
./install.sh
```

Then run from anywhere:
```bash
create-github-oauth
create-google-oauth
```

### Update

To update to the latest version, pull the changes and run install again:

```bash
git pull
./install.sh
```

---

Both options will prompt you for configuration values and automatically save credentials to `.env`.

## Features

- **GitHub OAuth:**
  - Automatic OAuth app creation
  - Create DEV + PROD apps at once - Generate credentials for both environments simultaneously
  - Automatic client secret generation
  - Allow deletion of any existing app through the GitHub API

- **Google OAuth:**
  - Automatic OAuth 2.0 client ID creation
  - Automatic consent screen setup
  - Project selection/creation support
  - Support for Web and Desktop application types

- **Shared Features:**
  - **Flexible credential output:**
    - Copy to clipboard (Mac/Linux)
    - Write to `.env`, `.env.local`, or `.env.production`
  - **Smart duplicate handling** - Never overwrites existing keys, uses `GENERATED_` prefixes  

## How it works

GitHub deprecated the API endpoint for creating new OAuth apps. This tool:

1. Opens a browser (headless or visible).  
2. Navigates to verified GitHub URLs.  
3. Fills out the form with your config.  
4. Generates a client secret.  
5. Saves the credentials to your `.env` file automatically.  

## Configuration

The `./setup.sh` script will create a `.env` file for you. For GitHub:

```ini
OAUTH_APP_NAME="My App"
GITHUB_PASSWORD="your-password"             # Optional - for auto-filling Sudo Mode
OAUTH_BASE_URL="http://localhost:3000"
OAUTH_CALLBACK_URL="http://localhost:3000/api/auth/callback/github"
OAUTH_PROD_BASE_URL="https://your-production-domain.com"  # For DEV+PROD mode
OAUTH_PROD_CALLBACK_URL="https://your-production-domain.com/api/auth/callback/github"
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
- **Anything else**: I also don’t know. Any agent will fix it.  

---

xxx,
Remco Stoeten

Stars will make my e-penor grow, so please do.
