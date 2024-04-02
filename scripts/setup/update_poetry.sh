#!/bin/bash

# Check if version argument is provided
if [ -z "$1" ]
then
    echo "No argument supplied. Please provide the Poetry version to check."
    exit 1
fi

echo "Checking Pipx installation..."

# Check if pipx is installed
if ! command -v pipx &> /dev/null
then
    echo "Pipx is not installed. Installing..."
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    echo "Pipx installed successfully."
else
    echo "Pipx is already installed."
fi

echo "Checking Poetry installation..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry is not installed. Installing..."
    pipx install poetry
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

# Check if poetry-monorepo-dependency-plugin is installed
if poetry self show | grep -q "poetry-monorepo-dependency-plugin"; then
    echo "poetry-monorepo-dependency-plugin is already installed."
else
    echo "Installing poetry-monorepo-dependency-plugin..."
    poetry run pip install poetry-monorepo-dependency-plugin
    echo "poetry-monorepo-dependency-plugin installed successfully."
fi