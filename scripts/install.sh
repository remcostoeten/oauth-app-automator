#!/bin/bash

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║   🔐  GitHub OAuth Automator - Global Install / Update    ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

if ! command -v uv &> /dev/null; then
    echo -e "  ${RED}✗${NC} uv is not installed. Run ./setup.sh first."
    exit 1
fi

echo -e "  ${CYAN}This will install or update the following command globally:${NC}"
echo -e "    • ${GREEN}oauth-automator${NC} - Unified OAuth automation tool"
echo ""
echo -e "  ${YELLOW}Installation location:${NC} ~/.local/bin/"
echo ""

read -p "  Continue? [Y/n] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo -e "  ${YELLOW}Cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "  ${CYAN}▶${NC} Installing/Updating with uv..."

uv tool install --editable .

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Installation complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  You can now run from anywhere:"
echo -e "    ${CYAN}oauth-automator${NC}"
echo ""

# macOS specific advice
if [[ "$(uname)" == "Darwin" ]]; then
    echo -e "  ${YELLOW}macOS Note:${NC} If not in PATH, add this to ~/.zprofile or ~/.zshrc:"
    echo -e "    ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
else
    echo -e "  ${YELLOW}Note:${NC} Make sure ${CYAN}~/.local/bin${NC} is in your PATH"
fi

echo ""
echo -e "  To uninstall:"
echo -e "    ${CYAN}uv tool uninstall oauth-automator${NC}"
echo ""
