#!/bin/bash

# Default value for the --ui flag
ui=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --ui)
            ui=true
            shift
            ;;
        *)
            echo "Unknown option: $key"
            exit 1
            ;;
    esac
    shift
done

# Function to forcibly terminate a process by port
terminate_process_by_port() {
    port="$1"
    echo "Terminating process on port: $port"
    fuser -k -n tcp "$port"  # Forcefully terminate processes using the specified port
    echo "Process terminated."
}

# Trap signals to ensure cleanup on script termination
trap 'terminate_process_by_port 7860; terminate_process_by_port 3000' EXIT

# install playwright if there is not installed yet
npx playwright install

# Navigate to the project root directory (where the Makefile is located)
cd ../../

# Start the frontend using 'make frontend' in the background
make frontend &

# Give some time for the frontend to start (adjust sleep duration as needed)
sleep 10

# Navigate to the test directory
cd src/frontend

# Run frontend only Playwright tests with or without UI based on the --ui flag
if [ "$ui" = true ]; then
    PLAYWRIGHT_HTML_REPORT=playwright-report/onlyFront npx playwright test tests/onlyFront --ui --project=chromium
else
    PLAYWRIGHT_HTML_REPORT=playwright-report/onlyFront npx playwright test tests/onlyFront --project=chromium
fi

# Navigate back to the project root directory
cd ../../

# Start the backend using 'make backend' in the background
make backend &

# Give some time for the backend to start (adjust sleep duration as needed)
sleep 25

# Navigate back to the test directory
cd src/frontend

# Run Playwright tests with or without UI based on the --ui flag
if [ "$ui" = true ]; then
    PLAYWRIGHT_HTML_REPORT=playwright-report/e2e npx playwright test tests/end-to-end --ui --project=chromium
else
    PLAYWRIGHT_HTML_REPORT=playwright-report/e2e npx playwright test tests/end-to-end --project=chromium
fi

npx playwright show-report

# After the tests are finished, you can add cleanup or teardown logic here if needed

# The trap will automatically terminate processes by port on script exit
