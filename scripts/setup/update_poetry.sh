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

echo "Detected Operating System: $OS"

# Installation of pipx based on the detected OS
install_pipx() {
    case $1 in
        macOS)
            # macOS installation using Homebrew
            command -v brew >/dev/null 2>&1 || exit_with_message "Homebrew is not installed. Please install Homebrew first."
            echo "Installing pipx using Homebrew..."
            brew install pipx
            pipx ensurepath
            ;;
        Linux)
            # Linux installation. Further checks are needed to distinguish between distributions
            if grep -qEi "(ubuntu|debian)" /etc/*release; then
                echo "Installing pipx on Ubuntu/Debian..."
                sudo apt update
                sudo apt install pipx -y
            elif grep -qEi "fedora" /etc/*release; then
                echo "Installing pipx on Fedora..."
                sudo dnf install pipx -y
            else
                echo "Installing pipx using pip (other Linux distributions)..."
                python3 -m pip install --user pipx
            fi
            pipx ensurepath
            ;;
        *)
            exit_with_message "Unsupported operating system for pipx installation."
            ;;
    esac
}

# Function to fetch the latest version of pipx from GitHub and compare with the installed version
check_for_pipx_update() {
    echo "Checking for updates to pipx..."
    # Fetch the latest version of pipx, ensuring only to capture the numeric version without 'v' prefix.
    local latest_version=$(curl -s https://api.github.com/repos/pypa/pipx/releases/latest | grep '"tag_name":' | sed -E 's/.*"tag_name": "v?([^"]+)".*/\1/')
    # Extract the current installed version of pipx.
    local current_version=$(pipx --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

    if [[ "$latest_version" == "$current_version" ]]; then
        echo "You have the latest version of pipx ($current_version)."
    else
        echo "A newer version of pipx ($latest_version) is available. You have $current_version. Do you want to update? (yes/no)"
        read -r user_input
        if [[ "$user_input" == "yes" ]]; then
            echo "Updating pipx..."
            case "$OS" in
                macOS)
                    brew upgrade pipx
                    ;;
                Linux)
                    if grep -qEi "(ubuntu|debian)" /etc/*release; then
                        sudo apt update
                        sudo apt install --only-upgrade pipx -y
                    elif grep -qEi "fedora" /etc/*release; then
                        sudo dnf upgrade pipx -y
                    else
                        python3 -m pip install --user --upgrade pipx
                    fi
                    ;;
                *)
                    exit_with_message "Unsupported operating system for pipx update."
                    ;;
            esac
            pipx ensurepath
            echo "pipx updated to version $latest_version"
        else
            echo "Not updating pipx at this time."
        fi
    fi
}

# Now, modify the existing check to call check_for_pipx_update even if pipx is installed
if ! command -v pipx &> /dev/null; then
    echo "Pipx is not installed. Installing..."
    install_pipx "$OS"
    echo "Pipx installed successfully."
else
    echo "Pipx is already installed."
    check_for_pipx_update
fi


echo "Checking Poetry installation..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry is not installed. Installing..."
    # Also install python 3.10 and use
    pipx install poetry --python python3.10  --fetch-missing-python
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

