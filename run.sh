#!/bin/bash
# GitHub OAuth Automator - Runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-detect venv
if [ -d "${SCRIPT_DIR}/.venv" ]; then
    PYTHON_CMD="${SCRIPT_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Forward all arguments to the python module
# If no arguments are provided, it launches the interactive menu
exec PYTHONPATH="${SCRIPT_DIR}/src" "$PYTHON_CMD" -m oauth_automator "$@"
