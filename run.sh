#!/bin/bash
# GitHub OAuth Automator - Runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_DIR="${SCRIPT_DIR}/.venv"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
DEPS_MARKER="${VENV_DIR}/.deps_installed"

if command -v uv >/dev/null 2>&1; then
    UV_CMD="uv"
else
    UV_CMD=""
fi

# Ensure venv exists (prefer uv if available)
if [ ! -d "${VENV_DIR}" ]; then
    if [ -n "${UV_CMD}" ]; then
        "${UV_CMD}" venv "${VENV_DIR}"
    else
        python3 -m venv "${VENV_DIR}"
    fi
fi

PYTHON_CMD="${VENV_DIR}/bin/python3"

# Install/update dependencies when requirements.txt changes
if [ -f "${REQ_FILE}" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        CURRENT_HASH="$(sha256sum "${REQ_FILE}" | awk '{print $1}')"
    else
        CURRENT_HASH="$(cksum "${REQ_FILE}" | awk '{print $1}')"
    fi

    INSTALLED_HASH=""
    if [ -f "${DEPS_MARKER}" ]; then
        INSTALLED_HASH="$(cat "${DEPS_MARKER}")"
    fi

    if [ "${CURRENT_HASH}" != "${INSTALLED_HASH}" ]; then
        if [ -n "${UV_CMD}" ]; then
            "${UV_CMD}" pip install -r "${REQ_FILE}" --python "${PYTHON_CMD}"
        else
            "${PYTHON_CMD}" -m pip install -r "${REQ_FILE}"
        fi
        echo "${CURRENT_HASH}" > "${DEPS_MARKER}"
    fi
fi

# Forward all arguments to the python module
# If no arguments are provided, it launches the interactive menu
exec "$PYTHON_CMD" -m src.oauth_automator "$@"
