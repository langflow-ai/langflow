#!/bin/bash

# Default value for the --ui flag
ui=false

# Absolute path to the project root directory
PROJECT_ROOT="../../"

# Check if necessary commands are available
for cmd in npx poetry fuser; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: Required command '$cmd' is not installed. Aborting."
        exit 1
    fi
done

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
    if ! fuser -k -n tcp "$port"; then
        echo "Failed to terminate process on port $port. Please check manually."
    else
        echo "Process terminated."
    fi
}

delete_temp() {
    if cd "$PROJECT_ROOT"; then
        echo "Deleting temp database"
        rm -f temp && echo "Temp database deleted." || echo "Failed to delete temp database."
    else
        echo "Failed to navigate to project root for cleanup."
    fi
}

# Trap signals to ensure cleanup on script termination
trap 'terminate_process_by_port 7860; terminate_process_by_port 3000; delete_temp' EXIT

# Ensure the script is executed from the project root directory
if ! cd "$PROJECT_ROOT"; then
    echo "Error: Failed to navigate to project root directory. Aborting."
    exit 1
fi

# Install playwright if not installed yet
if ! npx playwright install; then
    echo "Error: Failed to install Playwright. Aborting."
    exit 1
fi

# Start the frontend
make frontend > /dev/null 2>&1 &

# Adjust sleep duration as needed
sleep 10

# Install backend dependencies
if ! poetry install; then
    echo "Error: Failed to install backend dependencies. Aborting."
    exit 1
fi

# Start the backend
LANGFLOW_DATABASE_URL=sqlite:///./temp LANGFLOW_AUTO_LOGIN=True poetry run langflow run --backend-only --port 7860 --host 0.0.0.0 --no-open-browser > /dev/null 2>&1 &
backend_pid=$!  # Capture PID of the backend process
# Adjust sleep duration as needed
sleep 25

# Navigate to the test directory
if ! cd src/frontend; then
    echo "Error: Failed to navigate to test directory. Aborting."
    kill $backend_pid  # Terminate the backend process if navigation fails
    echo "Backend process terminated."
    exit 1
fi

# Check if backend is running
if ! lsof -i :7860; then
    echo "Error: Backend is not running. Aborting."
    exit 1
fi

# Run Playwright tests
if [ "$ui" = true ]; then
    TEST_COMMAND="npx playwright test tests/core --ui --project=chromium"
else
    TEST_COMMAND="npx playwright test tests/core --project=chromium"
fi

if ! PLAYWRIGHT_HTML_REPORT=playwright-report/e2e $TEST_COMMAND; then
    echo "Error: Playwright tests failed. Aborting."
    exit 1
fi

if [ "$ui" = true ]; then
    echo "Opening Playwright report..."
    npx playwright show-report
fi


trap 'terminate_process_by_port 7860; terminate_process_by_port 3000; delete_temp; kill $backend_pid 2>/dev/null' EXIT