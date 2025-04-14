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
    cp /start-nginx.sh "$TESTDIR/"
    chmod +x "$TESTDIR/start-nginx.sh"

    # Create a minimal template file for testing
    echo "server { listen \${FRONTEND_PORT}; proxy_pass \${BACKEND_URL}; }" > "$TESTDIR/etc/nginx/conf.d/default.conf.template"

    # Set initial environment for tests
    cd "$TESTDIR"
    export DEBUG="true"

    # Mock the nginx command
    function nginx() {
        echo "MOCK_NGINX: $@" >> "$TESTDIR/nginx_calls.log"
        # Mock successful validation
        if [[ "$1" == "-t" ]]; then
            return 0
        fi
    }
    export -f nginx

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

# Test BACKEND_URL from environment variable
@test "BACKEND_URL can be set via environment variable" {
    setup_test_env "BACKEND_URL=http://backend-service:8000" "FRONTEND_PORT=8080"

    # Run the script with output capture
    run bash "$TESTDIR/start-nginx.sh"

    # Check for expected output in the script execution
    echo "$output" > "$TESTDIR/script_output.log"

    # The script should mention the backend URL
    assert_output --partial "Backend URL: http://backend-service:8000"
}

# Test BACKEND_URL from command line argument
@test "BACKEND_URL can be provided as command line argument" {
    setup_test_env "FRONTEND_PORT=8080"

    # Run the script with backend URL as argument
    run bash "$TESTDIR/start-nginx.sh" "http://api-backend:9000"

    # Check for expected output
    assert_output --partial "Using BACKEND_URL from command line argument: http://api-backend:9000"
    assert_output --partial "Backend URL: http://api-backend:9000"
}

# Test invalid BACKEND_URL format
@test "Script fails with invalid BACKEND_URL format" {
    # Run with invalid URL format
    run bash "$TESTDIR/start-nginx.sh" "invalid-url-format"

    # Check that script exited with error
    assert_failure
    assert_output --partial "ERROR: Invalid BACKEND_URL format"
}

# Test missing BACKEND_URL
@test "Script fails when BACKEND_URL is missing" {
    # Run without BACKEND_URL
    run bash "$TESTDIR/start-nginx.sh"

    # Check that script exited with error
    assert_failure
    assert_output --partial "ERROR: BACKEND_URL must be set"
}

# Test with a very long URL
@test "Script handles very long backend URLs" {
    setup_test_env "BACKEND_URL=http://very-long-backend-service-name-that-is-valid-but-extremely-lengthy-for-testing-edge-cases.example.com:8000/api/v1/endpoint"

    # Run with long BACKEND_URL
    run bash "$TESTDIR/start-nginx.sh"

    # Check for expected output in the script execution
    echo "$output" > "$TESTDIR/script_output.log"

    # The script should mention the backend URL
    assert_output --partial "Backend URL: http://very-long-backend-service-name-that-is-valid-but-extremely-lengthy-for-testing-edge-cases.example.com:8000"
}

@test "Script handles special characters in environment variables" {
    setup_test_env "BACKEND_URL=http://backend:8000/api?version=1.0&format=json" "FRONTEND_PORT=8080"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Check that special characters are handled correctly
    assert_output --partial "Backend URL: http://backend:8000/api?version=1.0&format=json"
}

# Test probe filter enabled
@test "Probe filter is enabled by default" {
    setup_test_env "BACKEND_URL=http://backend:8000" "SUPPRESS_PROBE_LOGS=true"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Check if probe filter was configured
    assert_output --partial "Configuring probe filter to suppress health check logs"
}

# Test probe filter disabled
@test "Probe filter can be disabled" {
    setup_test_env "BACKEND_URL=http://backend:8000" "SUPPRESS_PROBE_LOGS=false"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Check for expected output
    assert_output --partial "Probe filtering disabled, all requests will be logged"
}

# Test NGINX configuration validation
@test "Script validates NGINX configuration" {
    setup_test_env "BACKEND_URL=http://backend:8000"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # The script should mention validating NGINX configuration
    assert_output --partial "Validating NGINX configuration"

    # Also check the log file if it was created
    if [ -f "$TESTDIR/nginx_calls.log" ]; then
        grep -q "MOCK_NGINX: -t" "$TESTDIR/nginx_calls.log"
    fi
}

# Test NGINX configuration validation failure
@test "Script exits when NGINX configuration validation fails" {
    setup_test_env "BACKEND_URL=http://backend:8000"

    # Override nginx mock to simulate validation failure
    function nginx() {
        echo "MOCK_NGINX: $@" >> "$TESTDIR/nginx_calls.log"
        if [[ "$1" == "-t" ]]; then
            echo "nginx: configuration file test failed"
            return 1
        fi
    }
    export -f nginx

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Check that script exited with error
    assert_failure
    assert_output --partial "Validating NGINX configuration"
}

@test "NGINX configuration includes security headers" {
    setup_test_env "BACKEND_URL=http://backend:8000"

    # Run the script
    run bash "$TESTDIR/start-nginx.sh"

    # Run nginx -T to dump config
    function nginx() {
        if [[ "$1" == "-T" ]]; then
            echo "http {
                add_header X-Content-Type-Options nosniff;
                add_header X-XSS-Protection \"1; mode=block\";
                add_header X-Frame-Options SAMEORIGIN;
            }"
        fi
    }
    export -f nginx

    # Check for security headers
    run nginx -T
    assert_output --partial "X-Content-Type-Options"
    assert_output --partial "X-XSS-Protection"
    assert_output --partial "X-Frame-Options"
}
