#!/bin/sh
# Runtime environment variable injection for AI Studio Frontend
# Based on genesis-frontend pattern - line endings must be \n, not \r\n !
set -e

echo "INFO: Generating AI Studio Frontend environment configuration..."

# Determine output directory (for container use /usr/share/nginx/html, for testing use dist)
OUTPUT_DIR="/usr/share/nginx/html"
if [ ! -d "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="./dist"
    mkdir -p "$OUTPUT_DIR"
fi

ENV_FILE="${OUTPUT_DIR}/.env.example"
if [ ! -f "$ENV_FILE" ]; then
    ENV_FILE="./.env.example"
fi

# Create the output file with opening bracket
echo "window._env_ = Object.freeze({" > "${OUTPUT_DIR}/env-config.js"

# Process the .env.example file
awk -F '=' '
!/^#/ && NF > 1 {
    # Get the variable name (first field) and trim whitespace
    var_name=$1
    gsub(/^[ \t]+|[ \t]+$/, "", var_name)

    if (var_name != "") {
        # Check if environment variable exists using a more reliable method
        cmd = "if [ -n \"${" var_name "+x}\" ]; then echo \"${" var_name "}\"; else echo \"__NOT_SET__\"; fi"
        cmd | getline env_value
        close(cmd)

        # Output the variable name with either its environment value or empty string
        if (env_value != "__NOT_SET__") {
            # Escape any quotes in the value
            gsub(/"/, "\\\"", env_value)
            printf "  %s: \"%s\",\n", var_name, env_value
        } else {
            printf "  %s: \"\",\n", var_name
        }
    }
}' "$ENV_FILE" >> "${OUTPUT_DIR}/env-config.js"

# Close the object
echo "})" >> "${OUTPUT_DIR}/env-config.js"

echo "INFO: Generated env-config.js with environment variables for AI Studio."
echo "INFO: Environment variables processed from .env.example"

# Show a summary of what was generated (for debugging)
if [ "${VITE_DEBUG_MODE:-false}" = "true" ]; then
    echo "DEBUG: Generated env-config.js content:"
    cat "${OUTPUT_DIR}/env-config.js"
fi