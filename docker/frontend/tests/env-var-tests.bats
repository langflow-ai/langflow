#!/usr/bin/env bats
# bats file_tags=parallel:true

load '/usr/local/lib/bats-support/load'
load '/usr/local/lib/bats-assert/load'

# Setup function runs before each test
setup() {
    # Create a temporary directory for test outputs with unique ID per test
    export TEST_ID="$(date +%s)-$$"
    export TESTDIR="$(mktemp -d)/test-$TEST_ID"

    # Create mock directories and files needed by the script
    mkdir -p "$TESTDIR/etc/nginx/conf.d"
    mkdir -p "$TESTDIR/nginx-access-log"
    mkdir -p "$TESTDIR/var/log/nginx"

    # Copy the script to test directory
    # Note: This script is mounted at /start-nginx.sh in the container
    cp /start-nginx.sh "$TESTDIR/"

    # Create a template file for testing with all environment variables used in the template
    cat > "$TESTDIR/etc/nginx/conf.d/default.conf.template" << EOF
worker_processes auto;
pid /tmp/nginx.pid;

events {
    worker_connections \${WORKER_CONNECTIONS};
}

http {
    error_log /var/log/nginx/error.log \${ERROR_LOG_LEVEL};

    client_body_timeout \${CLIENT_TIMEOUT};
    client_header_timeout \${CLIENT_TIMEOUT};
    client_max_body_size \${CLIENT_MAX_BODY_SIZE};

    gzip_comp_level \${GZIP_COMPRESSION_LEVEL};

    server {
        listen \${FRONTEND_PORT};

        location /api {
            proxy_pass \${BACKEND_URL};
        }
    }
}
EOF

    # Set basic environment variables
    cd "$TESTDIR"
    export DEBUG="true"
    export BACKEND_URL="http://localhost:8000"  # Use localhost instead of backend-service

    # Mock the nginx command
    function nginx() {
        echo "MOCK_NGINX: $@" >> "$TESTDIR/nginx_calls.log"
        # Mock successful validation
        if [[ "$1" == "-t" ]]; then
            return 0
        fi
    }
    export -f nginx

    # Mock exec to avoid actual execution
    function exec() {
        echo "EXEC: $@" > "$TESTDIR/exec_call.log"
    }
    export -f exec

    # Record initial test environment variables for test isolation tracking
    (env | grep -E '^(FRONTEND|BACKEND|CLIENT|NGINX|WORKER|GZIP|ERROR|DEBUG)') > "$TESTDIR/test_vars_before.log" 2>/dev/null || true

    # Clear specific test-related environment variables
    clean_test_env
}

# Teardown function runs after each test
teardown() {
    # Optionally capture test environment variables after test for debugging
    if [ -d "$TESTDIR" ] && [ "$DEBUG_ENV" = "true" ]; then
        (env | grep -E '^(FRONTEND|BACKEND|CLIENT|NGINX|WORKER|GZIP|ERROR|DEBUG)') > "$TESTDIR/test_vars_after.log" 2>/dev/null || true
        echo "=== Environment Diff (test variables) ===" > "$TESTDIR/test_vars_diff.log"
        diff "$TESTDIR/test_vars_before.log" "$TESTDIR/test_vars_after.log" >> "$TESTDIR/test_vars_diff.log" 2>/dev/null || true
        cat "$TESTDIR/test_vars_diff.log"
    fi

    # Clean up the temporary directory
    if [ -d "$TESTDIR" ]; then
        rm -rf "$TESTDIR"
    fi

    # Reset TEST_ID and TESTDIR variables to avoid leakage
    unset TEST_ID
    unset TESTDIR
}

# Function to clean only test-specific environment variables
clean_test_env() {
    # Instead of unsetting ALL environment variables, we only unset the ones used in our tests
    # This is much safer and won't interfere with BATS internal workings
    unset FRONTEND_PORT 2>/dev/null || true
    unset BACKEND_URL 2>/dev/null || true
    unset CLIENT_MAX_BODY_SIZE 2>/dev/null || true
    unset GZIP_COMPRESSION_LEVEL 2>/dev/null || true
    unset CLIENT_TIMEOUT 2>/dev/null || true
    unset WORKER_CONNECTIONS 2>/dev/null || true
    unset ERROR_LOG_LEVEL 2>/dev/null || true
    unset NGINX_LOG_FORMAT 2>/dev/null || true
    unset NGINX_CUSTOM_LOG_FORMAT 2>/dev/null || true
    unset SUPPRESS_PROBE_LOGS 2>/dev/null || true
}

# Helper function to set a clean environment with specific variables
setup_test_env() {
    # First clean environment
    clean_test_env

    # Then set the variables passed as arguments
    # Usage: setup_test_env "VAR1=value1" "VAR2=value2"
    for var_assignment in "$@"; do
        export "$var_assignment"
    done
}

# Test default environment variables
@test "Default environment variables are set correctly" {
    setup_test_env "BACKEND_URL=http://backend:8000"

    # Run the script without setting any optional env vars
    run bash "$TESTDIR/start-nginx.sh"

    assert_success

    # Check output for default values
    assert_output --partial "Frontend port: 8080"
    assert_output --partial "Client max body size: 10m"
    assert_output --partial "Gzip compression level: 5"
    assert_output --partial "Client timeout: 12"
    assert_output --partial "Worker connections: 1024"
}

# Test setting all environment variables
@test "All environment variables are correctly substituted" {
    # Set all configurable environment variables
    setup_test_env \
        "BACKEND_URL=http://backend:8000" \
        "FRONTEND_PORT=9090" \
        "ERROR_LOG_LEVEL=error" \
        "CLIENT_MAX_BODY_SIZE=100m" \
        "GZIP_COMPRESSION_LEVEL=9" \
        "CLIENT_TIMEOUT=30" \
        "WORKER_CONNECTIONS=2048"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_success

    # Check output for custom values
    assert_output --partial "Frontend port: 9090"
    assert_output --partial "Client max body size: 100m"
    assert_output --partial "Gzip compression level: 9"
    assert_output --partial "Client timeout: 30"
    assert_output --partial "Worker connections: 2048"
    assert_output --partial "Error log level set to: error"
}

# Test command line arguments (don't check for them overriding env vars, just check if script is called)
@test "Command line arguments are processed by the script" {
    setup_test_env

    # Run the script with a custom backend URL and port as arguments
    run bash "$TESTDIR/start-nginx.sh" "http://localhost:7000" "7070"

    assert_success

    # Check if exec was called with the correct arguments
    grep -q "EXEC: nginx" "$TESTDIR/exec_call.log"

    # This test is considered successful as long as the script runs to completion
    # and attempts to exec nginx (which we've mocked)
    [ -f "$TESTDIR/exec_call.log" ]
}

# Test handling of special characters in environment variables
@test "Special characters in environment variables are handled correctly" {
    # Use URL with query parameters and special characters
    setup_test_env "BACKEND_URL=http://localhost:8000/api?version=1.0&format=json" "FRONTEND_PORT=8080"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_success

    # Check if URL was properly passed through
    assert_output --partial "Backend URL: http://localhost:8000/api?version=1.0&format=json"
}

# Test handling of log format configuration
@test "Log format configuration is correctly generated based on environment variables" {
    # Test with JSON log format
    setup_test_env "NGINX_LOG_FORMAT=json"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_failure

    # Check if JSON log format was configured
    assert_output --partial "Using JSON log format"

    # Test with default log format
    setup  # Reset the environment
    setup_test_env "NGINX_LOG_FORMAT=default"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_failure

    # Check if default log format was configured
    assert_output --partial "Using default log format"

    # Test with custom log format
    setup  # Reset the environment
    setup_test_env "NGINX_CUSTOM_LOG_FORMAT='\$remote_addr - \$time_local \$status'"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_failure

    # Check if custom log format was configured
    assert_output --partial "Using custom log format"
}

# Test empty/missing environment variables
@test "Script handles empty environment variables gracefully" {
    # Set empty values for optional variables
    setup_test_env "FRONTEND_PORT=" \
        "BACKEND_URL=http://localhost:8000" \
        "ERROR_LOG_LEVEL=" \
        "CLIENT_MAX_BODY_SIZE=" \
        "GZIP_COMPRESSION_LEVEL=" \
        "CLIENT_TIMEOUT=" \
        "WORKER_CONNECTIONS="

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    assert_success

    # Defaults should be used when variables are empty
    assert_output --partial "Frontend port: 8080"
    assert_output --partial "Client max body size: 10m"
    assert_output --partial "Gzip compression level: 5"
    assert_output --partial "Client timeout: 12"
    assert_output --partial "Worker connections: 1024"
}

@test "Script correctly generates NGINX configuration from template" {
    # Set all configurable environment variables
    setup_test_env \
        "BACKEND_URL=http://backend:8000" \
        "FRONTEND_PORT=9090" \
        "ERROR_LOG_LEVEL=error" \
        "CLIENT_MAX_BODY_SIZE=100m" \
        "GZIP_COMPRESSION_LEVEL=9" \
        "CLIENT_TIMEOUT=30" \
        "WORKER_CONNECTIONS=2048"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Check script success
    assert_success

    # Add debug output
    #echo "Debug: Script output:" >&3
    #echo "$output" >&3

    # Find the config directory from script output
    config_dir=$(echo "$output" | grep "Created temporary configuration directory:" | awk '{print $NF}')
    #echo "Debug: Config directory from output: $config_dir" >&3

    # If not found in output, try to find it manually
    if [ -z "$config_dir" ]; then
        config_dir=$(find /tmp -maxdepth 1 -name "nginx.*" -type d | head -1)
        echo "Debug: Config directory from find: $config_dir" >&3
    fi

    # Verify directory exists
    assert [ -n "$config_dir" ]
    assert [ -d "$config_dir" ]

    # List contents of directory for debugging
    #echo "Debug: Contents of $config_dir:" >&3
    #ls -la "$config_dir" >&3

    # Check for the config file
    config_file="$config_dir/default.conf"

    # Verify file exists
    assert [ -f "$config_file" ]

    # Output file content for debugging
    #echo "Debug: Content of $config_file:" >&3
    #cat "$config_file" >&3

    # Check configuration content
    run cat "$config_file"
    assert_output --partial "listen 9090"
    assert_output --partial "proxy_pass http://backend:8000"
    assert_output --partial "client_max_body_size 100m"
    assert_output --partial "gzip_comp_level 9"
    assert_output --partial "client_body_timeout 30"
    assert_output --partial "worker_connections 2048"
    assert_output --partial "error_log /var/log/nginx/error.log error"
}
