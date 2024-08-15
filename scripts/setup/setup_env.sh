#!/bin/bash

# Create a .env if it doesn't exist, log all cases
if [ ! -f .env ]; then
  echo "Creating .env file"
  touch .env
else
  # do nothing and do not log
  true
fi
