#!/bin/bash

# GitHub OAuth Automator - Interactive Setup
# Guides users through the complete setup process.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║   🔐  GitHub OAuth Automator - Setup                       ║"
    echo "║       Let's get you up and running!                        ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_step() { echo -e "\n${BLUE}▶${NC} ${BOLD}$1${NC}"; }
log_ok() { echo -e "  ${GREEN}✓${NC} $1"; }
log_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "  ${RED}✗${NC} $1"; }
prompt() { echo -en "  ${CYAN}➤${NC} $1: "; }

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check uv is installed (it handles everything else)
# ─────────────────────────────────────────────────────────────────────────────
check_uv() {
    log_step "Checking for uv..."
    
    if command -v uv &> /dev/null; then
        log_ok "Found: $(uv --version)"
        prompt "Check for uv updates? [y/N]"
        read -r response
        if [[ "${response,,}" =~ ^(y|yes)$ ]]; then
            log_step "Updating uv..."
            uv self update || true
        fi
        return 0
    fi
    
    log_warn "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Source the new path
    export PATH="$HOME/.local/bin:$PATH"
    
    if command -v uv &> /dev/null; then
        log_ok "Installed: $(uv --version)"
    else
        log_error "Failed to install uv"
        echo ""
        echo -e "  ${BOLD}Manual install:${NC}"
        echo -e "    curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Check for a browser (Playwright needs one)
# ─────────────────────────────────────────────────────────────────────────────
check_browser() {
    log_step "Checking for browser..."
    
    # 1. Check for system browsers
    browsers=(
        "/usr/bin/google-chrome"
        "/usr/bin/chromium"
        "/usr/bin/chromium-browser"
        "/usr/bin/brave-browser"
        "/snap/bin/chromium"
    )
    
    for browser in "${browsers[@]}"; do
        if [[ -x "$browser" ]]; then
            log_ok "Found system browser: $browser"
            return 0
        fi
    done
    
    # 2. Check if playwright already has a browser installed
    if uv run --with playwright python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" &> /dev/null; then
        log_ok "Found Playwright Chromium"
        return 0
    fi

    log_warn "No system Chrome/Chromium found."
    echo -e "  Playwright will download its own Chromium (~150MB)."
    prompt "Continue? [Y/n]"
    read -r response
    
    if [[ "${response,,}" =~ ^(n|no)$ ]]; then
        exit 1
    fi
    
    log_ok "Will use Playwright's bundled Chromium"
    return 1 # Signal that we need to install it
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Install Playwright browser
# ─────────────────────────────────────────────────────────────────────────────
install_playwright() {
    # If check_browser returned 0, we skip this
    if check_browser; then
        log_ok "Skipping browser installation (already present)"
        return 0
    fi

    log_step "Setting up Playwright browser..."
    echo "  Installing Chromium (this may take a minute)..."
    uv run --with playwright python -m playwright install chromium
    log_ok "Playwright Chromium ready"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Configure .env file
# ─────────────────────────────────────────────────────────────────────────────
configure_env() {
    log_step "Configuring environment variables..."
    
    if [[ -f "$ENV_FILE" ]]; then
        log_warn ".env file already exists"
        prompt "Overwrite it? [y/N]"
        read -r response
        if [[ ! "${response,,}" =~ ^(y|yes)$ ]]; then
            log_ok "Keeping existing .env"
            return 0
        fi
    fi
    
    echo ""
    echo -e "  ${BOLD}Let's configure your OAuth app settings:${NC}"
    echo -e "  ${YELLOW}(Press Enter to accept defaults in brackets)${NC}"
    echo ""
    
    prompt "OAuth App Name [my-oauth-app]"
    read -r app_name
    app_name="${app_name:-my-oauth-app}"
    
    prompt "App Description [Created via automation]"
    read -r app_desc
    app_desc="${app_desc:-Created via automation}"
    
    prompt "Homepage URL [http://localhost:3000]"
    read -r base_url
    base_url="${base_url:-http://localhost:3000}"
    
    default_callback="${base_url}/api/auth/callback/github"
    prompt "Callback URL [${default_callback}]"
    read -r callback_url
    callback_url="${callback_url:-$default_callback}"
    
    # Production settings
    echo ""
    echo -e "  ${BOLD}Production Settings (for Dual Mode):${NC}"
    prompt "Prod Base URL [https://your-domain.com]"
    read -r prod_base_url
    prod_base_url="${prod_base_url:-https://your-domain.com}"
    
    default_prod_callback="${prod_base_url}/api/auth/callback/github"
    prompt "Prod Callback URL [${default_prod_callback}]"
    read -r prod_callback_url
    prod_callback_url="${prod_callback_url:-$default_prod_callback}"
    
    # Browser profile configuration
    echo ""
    echo -e "  ${BOLD}Browser Profile Configuration:${NC}"
    echo ""
    echo -e "  ${CYAN}What is this?${NC}"
    echo -e "  Your browser stores login sessions in a 'profile' folder."
    echo -e "  If you're already logged into GitHub in Brave/Chrome, we can"
    echo -e "  reuse that session - no need to log in again!"
    echo ""
    echo -e "  ${YELLOW}⚠️  Important: Close Brave/Chrome before running the automation!${NC}"
    echo ""
    
    browser_profile=""
    browser_executable=""
    
    # Try to autodetect common profile paths & executables
    brave_profile="$HOME/.config/BraveSoftware/Brave-Browser/Default"
    chrome_profile="$HOME/.config/google-chrome/Default"
    brave_exe="/usr/bin/brave-browser"
    chrome_exe="/usr/bin/google-chrome"
    
    has_brave=false
    has_chrome=false
    [[ -d "$brave_profile" ]] && has_brave=true
    [[ -d "$chrome_profile" ]] && has_chrome=true
    
    # Intelligent Selection Logic
    if $has_brave && $has_chrome; then
        echo -e "  ${GREEN}✓${NC} Found both Brave and Chrome profiles!"
        echo -e "    [1] Brave (${CYAN}$brave_profile${NC})"
        echo -e "    [2] Chrome (${CYAN}$chrome_profile${NC})"
        echo ""
        prompt "Which browser do you want to use? [1/2]"
        read -r choice
        
        if [[ "$choice" == "2" ]]; then
            browser_profile="$chrome_profile"
            browser_executable="$chrome_exe"
        else
            browser_profile="$brave_profile"
            browser_executable="$brave_exe"
        fi
        
    elif $has_brave; then
        echo -e "  ${GREEN}✓${NC} Found Brave profile: ${CYAN}$brave_profile${NC}"
        prompt "Use this Brave profile? [Y/n]"
        read -r response
        if [[ ! "${response,,}" =~ ^(n|no)$ ]]; then
            browser_profile="$brave_profile"
            browser_executable="$brave_exe"
        fi
        
    elif $has_chrome; then
        echo -e "  ${GREEN}✓${NC} Found Chrome profile: ${CYAN}$chrome_profile${NC}"
        prompt "Use this Chrome profile? [Y/n]"
        read -r response
        if [[ ! "${response,,}" =~ ^(n|no)$ ]]; then
            browser_profile="$chrome_profile"
            browser_executable="$chrome_exe"
        fi
    fi
    
    # If no profile was auto-selected, offer manual entry
    if [[ -z "$browser_profile" ]]; then
        echo ""
        echo -e "  ${YELLOW}No browser profile auto-detected.${NC}"
        echo ""
        echo -e "  ${BOLD}How to find your profile manually:${NC}"
        echo -e "    1. Open Brave/Chrome"
        echo -e "    2. Go to ${CYAN}brave://version${NC} or ${CYAN}chrome://version${NC}"
        echo -e "    3. Look for ${CYAN}Profile Path${NC} - copy that path"
        echo ""
        prompt "Paste your profile path (or press Enter to skip)"
        read -r manual_profile
        
        if [[ -n "$manual_profile" && -d "$manual_profile" ]]; then
            browser_profile="$manual_profile"
            echo -e "  ${GREEN}✓${NC} Using custom profile: $browser_profile"
            
            # Try to guess executable for manual profile (best effort)
            if [[ "$manual_profile" == *"Brave"* ]]; then
                browser_executable="$brave_exe"
            elif [[ "$manual_profile" == *"hrome"* ]]; then
                browser_executable="$chrome_exe"
            fi
            
        elif [[ -n "$manual_profile" ]]; then
            echo -e "  ${RED}✗${NC} Path not found: $manual_profile"
            echo -e "  ${YELLOW}Skipping - will create fresh session.${NC}"
        else
            echo -e "  ${YELLOW}No profile selected - will create a fresh automation session.${NC}"
            echo -e "  ${YELLOW}You'll need to log into GitHub on first run.${NC}"
        fi
    fi
    
    echo ""
    echo -e "  ${YELLOW}Optional:${NC} GitHub password for automatic sudo-mode."
    echo -e "  ${YELLOW}Leave blank to enter manually when prompted.${NC}"
    prompt "GitHub Password (hidden)"
    read -rs github_pass
    echo ""

    echo ""
    echo -e "  ${BOLD}Secure Audit Logging:${NC}"
    echo -e "  Encrypted log of generated credentials in ~/.oauth-automator/github/"
    prompt "Enable secure logging? [y/N]"
    read -r enable_logging
    
    secure_logging="false"
    if [[ "${enable_logging,,}" =~ ^(y|yes)$ ]]; then
        secure_logging="true"
    fi
    
    cat > "$ENV_FILE" << EOF
# GitHub OAuth Automator Configuration
# Generated by setup.sh on $(date)

OAUTH_APP_NAME="${app_name}"
OAUTH_APP_DESCRIPTION="${app_desc}"
OAUTH_BASE_URL="${base_url}"
OAUTH_CALLBACK_URL="${callback_url}"
OAUTH_PROD_BASE_URL="${prod_base_url}"
OAUTH_PROD_CALLBACK_URL="${prod_callback_url}"
GITHUB_PASSWORD="${github_pass}"
ENABLE_SECURE_LOGGING="${secure_logging}"
BROWSER_PROFILE_PATH="${browser_profile}"
BROWSER_EXECUTABLE_PATH="${browser_executable}"
WRITE_ENV_FILE=true
EOF
    
    log_ok "Created .env file"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Offer to run
# ─────────────────────────────────────────────────────────────────────────────
offer_run() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Setup complete! You're ready to create OAuth apps.${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    prompt "Run the OAuth automator now? [Y/n]"
    read -r response
    
    if [[ ! "${response,,}" =~ ^(n|no)$ ]]; then
        echo ""
        exec "${SCRIPT_DIR}/run.sh"
    else
        echo ""
        echo -e "  To run later: ${CYAN}./run.sh${NC}"
        echo ""
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
main() {
    print_banner
    check_uv
    install_playwright
    configure_env
    offer_run
}

main
