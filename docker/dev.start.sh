#!/bin/bash

# Check if frontend should be built
if [ "$1" != "no-frontend" ]; then
    cd src/frontend \
        && rm -rf node_modules \
        && npm install \
        && npm run dev:docker &
fi

make backend
