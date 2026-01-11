#!/bin/bash
# Google OAuth Automator Runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-detect venv
if [ -d "${SCRIPT_DIR}/.venv" ]; then
    PYTHON_CMD="${SCRIPT_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Run the unified automator with 'google' as the first command
exec "$PYTHON_CMD" -m src.oauth_automator google "$@"
