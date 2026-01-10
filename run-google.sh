#!/bin/bash
# Google OAuth Automator Runner

# Load .env file if it exists
if [ -f .env ]; then
  while IFS='=' read -r key value; do
    # Skip comments and empty lines
    if [[ "$key" =~ ^#.*$ ]] || [[ -z "$key" ]]; then
      continue
    fi
    # Trim quotes if present (optional, but good practice if mixed styles)
    # value="${value%\"}"
    # value="${value#\"}"
    
    # Export securely
    export "$key=$value"
  done < .env
fi

# Check for virtual environment
if [ -d ".venv" ]; then
    PYTHON_CMD="./.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Run the Google OAuth automator
"$PYTHON_CMD" google_oauth_automator.py "$@"
