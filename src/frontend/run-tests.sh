#!/bin/bash

# Navigate to the project root directory (where the Makefile is located)
cd ../../

# Start the frontend using 'make frontend' in the background
make frontend &

# Give some time for the frontend to start (adjust sleep duration as needed)
sleep 10

#Run frontend only Playwright tests
cd src/frontend && npx playwright test --ui tests/onlyFront

# Start the backend using 'make backend' in the background
make backend &

# Give some time for the backend to start (adjust sleep duration as needed)
sleep 10

# Navigate back to the test directory
cd src/frontend

# Run Playwright tests
npx playwright test --ui tests/end-to-end

# After the tests are finished, you can add cleanup or teardown logic here if needed

# Terminate the background processes (backend and frontend)
pkill -f "make backend"
pkill -f "make frontend"
