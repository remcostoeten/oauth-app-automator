#!/bin/bash

# GitHub OAuth Automator - Interactive Setup
# Guides users through the complete setup process.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_ROOT}/.env"

# Colors
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
    echo "║   🔐  OAuth Automator - Setup                              ║"
    echo "║       Installing dependencies & preparing environment      ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_step() { echo -e "\n${BLUE}▶${NC} ${BOLD}$1${NC}"; }
log_ok() { echo -e "  ${GREEN}✓${NC} $1"; }
log_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

# 1. Setup Python Environment
setup_python() {
    log_step "Setting up Python environment..."

    if command -v uv &> /dev/null; then
        log_ok "Using uv for fast installation"
        if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
            uv venv "${PROJECT_ROOT}/.venv"
        fi
        uv pip install -e "${PROJECT_ROOT}"
    else
        log_warn "uv not found, using standard pip (slower)"
        python3 -m venv "${PROJECT_ROOT}/.venv"
        "${PROJECT_ROOT}/.venv/bin/pip" install -e "${PROJECT_ROOT}"
    fi
    
    # Install playwright browsers
    log_step "Installing Playwright browsers..."
    "${PROJECT_ROOT}/.venv/bin/python3" -m playwright install chromium
}

# 2. Basic .env setup
setup_env() {
    log_step "Checking configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        log_warn "No .env file found. Creating default..."
        cat > "$ENV_FILE" << EOF
# OAuth Automator API Configuration
# Created via setup.sh

# Optional: Browser Preferences
# BROWSER_EXECUTABLE_PATH=""
# BROWSER_PROFILE_PATH=""

# Defaults
OAUTH_BASE_URL="http://localhost:3000"
OAUTH_CALLBACK_URL="http://localhost:3000/api/auth/callback"
EOF
        log_ok "Created .env"
    else
        log_ok ".env already exists"
    fi
}

main() {
    print_banner
    setup_python
    setup_env
    
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Setup complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Run the tools with:"
    echo -e "    ${CYAN}./run.sh${NC} (Interactive Menu)"
    echo -e "    ${CYAN}./run.sh google create${NC} (Google Shortcut)"
    echo ""
}

main
