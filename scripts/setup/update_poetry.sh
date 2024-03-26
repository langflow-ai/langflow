#!/bin/bash

# Check if version argument is provided
if [ -z "$1" ]
then
    echo "No argument supplied. Please provide the Poetry version to check."
    exit 1
fi

echo "Checking Poetry version..."

# Check Poetry version
poetry_version=$(poetry --version | awk '{print $3}' | tr -d '()')
echo "Current Poetry version: $poetry_version"

# Compare version
if [[ "$(printf '%s\n' "$1" "$poetry_version" | sort -V | head -n1)" != "$1" ]]; then
    echo "Poetry version is lower than $1. Updating..."
    # Update Poetry
    poetry self update
    echo "Poetry updated successfully."
else
    echo "Poetry version is $1 or higher. No need to update."
fi