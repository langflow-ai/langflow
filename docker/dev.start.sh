#!/bin/bash

# Install frontend dependencies first (in foreground)
cd src/frontend \
&& rm -rf node_modules \
&& npm install

# Now start backend (npm install is complete, no more file changes, spares us from multiple backend restarts)
cd /app && make backend &

# Start frontend dev server
cd /app/src/frontend && npm run dev:docker
