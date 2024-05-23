#!/bin/bash

# Define the services and their corresponding docker compose service names
declare -A services
services=(
    ["langflowbase"]="backend frontend"
    ["discord"]="discord"
)

# Function to display the menu and get the user's choice
display_menu() {
    echo "Please choose an option:"
    echo "1) langflowbase"
    echo "2) langflowbase + discord"
    echo "3) exit"
    read -p "Enter your choice [1-3]: " choice
}

# Function to build and run the selected services
run_services() {
    local chosen_services=()
    for service in "${@}"; do
        chosen_services+=("${services[$service]}")
    done
    # Remove duplicates and run the chosen services
    IFS=" " read -r -a unique_services <<< "$(echo "${chosen_services[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' ')"
    docker compose up ${unique_services[@]}
}

while true; do
    display_menu
    case $choice in
        1)
            run_services "langflowbase"
            ;;
        2)
            run_services "langflowbase" "discord"
            ;;
        3)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid choice. Please enter a number between 1 and 3."
            ;;
    esac
done
