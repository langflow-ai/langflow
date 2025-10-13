#!/bin/bash
set -e

ENV_FILE=".env"

echo "Checking database setup..."

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found."
    echo "Please create a .env file with LANGFLOW_DATABASE_URL."
    echo "Example: LANGFLOW_DATABASE_URL=postgresql://postgres@localhost:5432/genesis_ai_studio_dev"
    exit 1
fi

# Extract LANGFLOW_DATABASE_URL from .env file
LANGFLOW_DATABASE_URL=$(grep "^LANGFLOW_DATABASE_URL=" "$ENV_FILE" 2>/dev/null | sed 's/.*=//' | head -1)

# Check if LANGFLOW_DATABASE_URL is set
if [ -z "$LANGFLOW_DATABASE_URL" ]; then
    echo "Error: LANGFLOW_DATABASE_URL not found in .env file."
    echo "Please add: LANGFLOW_DATABASE_URL=postgresql://postgres@localhost:5432/genesis_ai_studio_dev"
    exit 1
fi

echo "Found database URL: $LANGFLOW_DATABASE_URL"

# Parse the database URL
DB_URL="$LANGFLOW_DATABASE_URL"

# Extract components from URL
# Format: postgresql://user:password@host:port/database
DB_CREDENTIALS_HOST="${DB_URL#postgresql://}"
DB_USER_PASS="${DB_CREDENTIALS_HOST%%@*}"
DB_HOST_PORT_DB="${DB_CREDENTIALS_HOST#*@}"

# Extract user and password
if [[ "$DB_USER_PASS" == *:* ]]; then
    DB_USER="${DB_USER_PASS%%:*}"
    DB_PASSWORD="${DB_USER_PASS#*:}"
else
    DB_USER="$DB_USER_PASS"
    DB_PASSWORD=""
fi

# Extract host, port, database
DB_HOST_PORT="${DB_HOST_PORT_DB%%/*}"
DB_NAME="${DB_HOST_PORT_DB#*/}"

if [[ "$DB_HOST_PORT" == *:* ]]; then
    DB_HOST="${DB_HOST_PORT%%:*}"
    DB_PORT="${DB_HOST_PORT#*:}"
else
    DB_HOST="$DB_HOST_PORT"
    DB_PORT="5432"
fi

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql command not found."
    echo "Please install PostgreSQL:"
    echo "  On macOS: brew install postgresql"
    echo "  Then start the service: brew services start postgresql"
    exit 1
fi

# Build psql connection command
PSQL_CMD="psql"
if [ -n "$DB_HOST" ]; then
    PSQL_CMD="$PSQL_CMD -h $DB_HOST"
fi
if [ -n "$DB_PORT" ]; then
    PSQL_CMD="$PSQL_CMD -p $DB_PORT"
fi
if [ -n "$DB_USER" ]; then
    PSQL_CMD="$PSQL_CMD -U $DB_USER"
fi

# Set password if provided
if [ -n "$DB_PASSWORD" ]; then
    export PGPASSWORD="$DB_PASSWORD"
fi

# Check if database already exists
echo "Checking if database '$DB_NAME' exists..."
if $PSQL_CMD -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "Database '$DB_NAME' already exists and is set up."
    echo "Database setup complete!"
    exit 0
fi

echo "Database '$DB_NAME' not found. Creating..."

# Try to create the database
if createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" 2>/dev/null; then
    echo "Database '$DB_NAME' created successfully."
else
    echo "Error: Failed to create database '$DB_NAME'."
    echo "Please check:"
    echo "  1. PostgreSQL is running"
    echo "  2. User '$DB_USER' has permissions to create databases"
    echo "  3. The connection details in your .env file are correct"
    exit 1
fi

echo "Database setup complete!"
echo "Connected to: $LANGFLOW_DATABASE_URL"
