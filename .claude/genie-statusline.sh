#!/bin/bash

# 🧞 Genie Statusline Wrapper
# Allows running multiple statusline commands with proper formatting

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Read stdin once and store it
STDIN_DATA=$(cat)

# Check if we're running from npm package or local development
if [ -f "$PROJECT_ROOT/lib/statusline.js" ]; then
    # Local development - use local file
    echo "$STDIN_DATA" | node "$PROJECT_ROOT/lib/statusline.js"
else
    # Installed via npm - use npx
    echo "$STDIN_DATA" | npx -y automagik-genie statusline 2>/dev/null || echo "🧞 Genie statusline not found"
fi

# Only run automagik-genie statusline - no external tools