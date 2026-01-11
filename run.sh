#!/bin/bash
# GitHub OAuth Automator - Runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Autos-detect venv
if [ -d "${SCRIPT_DIR}/.venv" ]; then
    PYTHON_CMD="${SCRIPT_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Forward all arguments to the python module
# If no arguments are provided, it launches the interactive menu
exec "$PYTHON_CMD" -m src.oauth_automator "$@"
