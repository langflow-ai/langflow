#!/bin/bash

cd src/frontend \
    && rm -rf node_modules \
    && npm install \
    && npm run dev:docker &
make backend
