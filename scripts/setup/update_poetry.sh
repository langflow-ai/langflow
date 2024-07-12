#!/bin/bash

# Check if version argument is provided
if [ -z "$1" ]
then
    echo "No argument supplied. Please provide the Poetry version to check."
    exit 1
fi

# Utility function to display an error message and exit
exit_with_message() {
    echo "$1" >&2
    exit 1
}

# Check if version argument is provided
if [ -z "$1" ]; then
    exit_with_message "No argument supplied. Please provide the Poetry version to check."
fi

# Detect Operating System
OS="$(uname -s)"
case "$OS" in
    Darwin)
        OS="macOS"
        ;;
    Linux)
        OS="Linux"
        ;;
    *)
        exit_with_message "Unsupported operating system. This script supports macOS and Linux."
        ;;
esac


echo "Checking Poetry installation..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry is not installed. Installing..."
    # Also install python 3.10 and use
    curl -sSL https://install.python-poetry.org | python3 -
    echo "Poetry installed successfully."
else
    echo "Poetry is already installed."
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



