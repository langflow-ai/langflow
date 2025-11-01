#!/bin/bash

# Start frontend
cd src/frontend \
    && (rm -rf node_modules 2>/dev/null || echo "Warning: Could not remove node_modules, continuing...") \
    && npm install \
    && npm run dev:docker &
FRONTEND_PID=$!

# Wait a bit for frontend to start
sleep 5

# Check if frontend is still running
if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "Frontend started successfully (PID: $FRONTEND_PID)"
else
    echo "Frontend failed to start"
    exit 1
fi

# Start backend
make backend
