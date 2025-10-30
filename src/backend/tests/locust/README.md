# Langflow Load Testing

This directory contains comprehensive load testing tools for both Langflow and LFX APIs using Locust.

## 🔧 **Two Testing Systems**

### **Langflow API Testing** (Enhanced System)

- Files: `langflow_*.py`
- Tests the main Langflow application API
- Includes automatic setup, real starter projects, and comprehensive error logging

### **LFX API Testing** (Complex Serve)

- Files: `lfx_*.py`
- Tests the LFX complex serve API
- Uses traditional load testing patterns

## Features

- **Automatic Environment Setup**: Creates users, API keys, and test flows automatically
- **Pre-flight Testing**: Validates connectivity and flow execution before load testing
- **Multiple User Types**: Different user behaviors to simulate realistic load patterns
- **Load Test Shapes**: Predefined load patterns for different testing scenarios
- **Comprehensive Metrics**: Performance grading and detailed reporting
- **Enhanced Error Logging**: Detailed connection error analysis and Langflow log capture
- **Easy Setup**: One-command execution with automatic Langflow startup

## Quick Start

### Prerequisites

```bash
# Using uv (recommended)
uv add locust httpx

# Or using pip
pip install locust httpx
```

### Using Makefile Commands (Recommended)

The easiest way to use the load testing system:

```bash
# 1. Setup test environment (interactive flow selection)
make load_test_setup

# 2. Run a quick test
make load_test_langflow_quick

# 3. Run a full load test
make load_test_run

# 4. Clean up when done
make load_test_clean

# See all available commands
make load_test_help
```

## 🌐 **Remote Instance Testing**

For testing against a remote Langflow instance:

### Setup for Remote Testing

```bash
# Using Makefile (recommended)
make load_test_remote_setup LANGFLOW_HOST="https://your-remote-instance.com"
make load_test_remote_run LANGFLOW_HOST="https://your-remote-instance.com"

# Or using Python scripts directly
python langflow_setup_test.py --host https://your-remote-instance.com --interactive
python langflow_run_load_test.py --host https://your-remote-instance.com --no-start-langflow --headless --users 10 --duration 120

# Test remote instance before setup (optional)
python diagnose_remote.py --host https://your-remote-instance.com --load-test 5
```

### Important Notes for Remote Testing

- **Always use `--no-start-langflow`** when testing remote instances
- **Use HTTPS** for production remote instances
- **Consider network latency** in your performance expectations
- **Monitor both client and server resources** during testing
- **Use realistic user counts** based on your remote instance specs
- **Start with fewer users** (10 instead of 20) to avoid overwhelming remote instances
- **Use slower spawn rates** (1 user/sec) for more realistic load patterns
- **Status code 0 errors** indicate connection failures, usually from overloading the remote instance

### Two-Step Process

#### Step 1: Setup (Run Once)

Choose and set up a real Langflow starter project for testing:

```bash
# Interactive flow selection
python langflow_setup_test.py --interactive

# Use specific flow
python langflow_setup_test.py --flow "Memory Chatbot"

# List available flows
python langflow_setup_test.py --list-flows
```

This will:

- Use default Langflow credentials (langflow/langflow)
- Generate API keys
- Upload a real starter project flow
- Provide credentials for load testing

#### Step 2: Run Load Tests

```bash
# Interactive mode with web UI
python langflow_run_load_test.py

# Headless mode with 20 users for 2 minutes
python langflow_run_load_test.py --headless --users 20 --duration 120

# Use predefined load shape
python langflow_run_load_test.py --shape ramp100 --headless --users 100 --duration 180
```

### Advanced Usage

```bash
# Setup with custom host (e.g., remote instance)
python langflow_setup_test.py --host https://your-remote-instance.com --interactive

# Save credentials to file
python langflow_setup_test.py --interactive --save-credentials my_test_creds.json

# Test against existing remote Langflow instance
python langflow_run_load_test.py --host https://your-remote-instance.com --no-start-langflow

# Save results to CSV and HTML
python langflow_run_load_test.py --headless --csv results --html report.html --users 50 --duration 300

# Direct Locust usage (after setup)
export API_KEY="your-api-key-from-setup"
export FLOW_ID="your-flow-id-from-setup"
locust -f langflow_locustfile.py --host http://localhost:7860

# Distributed testing (master)
locust -f langflow_locustfile.py --host http://localhost:7860 --master

# Distributed testing (worker)
locust -f langflow_locustfile.py --host http://localhost:7860 --worker --master-host=localhost
```

## User Types

The load test includes multiple user types that simulate different usage patterns:

- **NormalUser** (default): Typical user behavior with realistic message distribution
- **AggressiveUser**: High-frequency requests with minimal wait times
- **SustainedLoadUser**: Constant 1 RPS per user for steady load testing
- **TailLatencyHunter**: Mixed workload to expose tail latency issues
- **ScalabilityTestUser**: Tests for scaling limits and performance cliffs
- **BurstUser**: Sends bursts of requests to test connection pooling

## Load Test Shapes

Predefined load patterns for different testing scenarios:

- **RampToHundred**: 0 → 100 users over 20 seconds, hold for 3 minutes
- **StepRamp**: Step increases every 30 seconds to find performance cliffs

Use with: `--shape ramp100` or `--shape stepramp`

## Environment Variables

- `LANGFLOW_HOST`: Base URL for Langflow server (default: http://localhost:7860)
- `SHAPE`: Load test shape (ramp100, stepramp)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30.0)

## Architecture

### Setup Process (`langflow_setup_test.py`)

1. **Health Check**: Verify Langflow is running
2. **Flow Selection**: Choose from 40+ real starter project flows
3. **Authentication**: Login with default credentials (langflow/langflow)
4. **API Key Generation**: Create API key for load testing
5. **Flow Upload**: Upload the selected starter project flow
6. **Credential Export**: Provide environment variables for testing

### Real Starter Project Flows

Instead of simple test flows, the system uses real Langflow starter projects:

- **Basic Prompting**: Simple LLM interaction
- **Memory Chatbot**: Conversational AI with memory
- **Document Q&A**: RAG-based document questioning
- **Research Agent**: Multi-step research workflows
- **Vector Store RAG**: Advanced retrieval-augmented generation
- **And 35+ more realistic flows**

This provides much more realistic load testing scenarios that exercise:

- Complex node graphs and dependencies
- Real LLM integrations
- Vector databases and embeddings
- Multi-step agent workflows
- Memory and state management

## Performance Grading

The load test provides automatic performance grading:

- **Grade A**: Excellent performance, production ready
- **Grade B**: Good performance with minor issues
- **Grade C**: Acceptable but monitor closely
- **Grade D**: Performance issues detected
- **Grade F**: Significant problems, not production ready

Grading is based on:

- Failure rate (< 1% for A grade)
- 95th percentile response time (< 10s for good grades)
- Request throughput and consistency

## Monitoring

The test tracks:

- Response times (p50, p95, p99)
- Request rates and throughput
- Failure rates and error types
- Slow requests (>10s, >20s)
- Connection and timeout issues

## Troubleshooting

### Common Issues

1. **Setup Failed**: Ensure Langflow is accessible and not in read-only mode
2. **Authentication Errors**: Verify default credentials (langflow/langflow) are enabled
3. **Flow Creation Failed**: Verify the user has permission to create flows
4. **Connection Errors**: Check network connectivity and firewall settings
5. **Status Code 0 Errors**: Usually indicates connection overload - reduce user count or spawn rate

### Debug Mode

For debugging, you can:

1. Run Langflow manually with `--log-level debug`
2. Check the Langflow logs for detailed error information
3. Use the web UI to verify the test flow was created correctly
4. Test API endpoints manually with curl or httpx
5. Use the diagnostic tool for remote instances: `python diagnose_remote.py --host <url> --load-test 10`

### Manual Setup

If automatic setup fails, you can set up manually:

1. Start Langflow: `python -m langflow run --auto-login`
2. Create a user account through the UI
3. Create an API key in the settings
4. Create a simple flow and note its ID
5. Set environment variables and run Locust directly

```bash
export API_KEY="your-api-key"
export FLOW_ID="your-flow-id"
locust -f langflow_locustfile.py --host http://localhost:7860
```

## Contributing

When adding new user types or test scenarios:

1. Inherit from `BaseLangflowUser`
2. Implement task methods with `@task` decorator
3. Use `self.make_request()` for consistent error handling
4. Add appropriate weight and wait_time settings
5. Document the user type's purpose and behavior

## Examples

### Basic Load Test

```bash
python langflow_run_load_test.py --headless --users 10 --duration 60
```

### Stress Test

```bash
python langflow_run_load_test.py --shape ramp100 --headless --users 100 --duration 300
```

### Performance Profiling

```bash
python langflow_run_load_test.py --shape stepramp --headless --csv profile_results
```

### Production Readiness Test

```bash
python langflow_run_load_test.py --users 50 --duration 600 --csv production_test --html production_report.html
```

## 📊 HTML Reports

The system generates beautiful HTML reports with:

- **Interactive Charts**: Response time graphs, throughput charts
- **Detailed Statistics**: Request/response metrics, percentiles
- **Error Analysis**: Failure breakdown and error patterns
- **Performance Timeline**: Real-time performance during the test
- **User Behavior Analysis**: Breakdown by user type and task

### HTML Report Examples

```bash
# Generate comprehensive HTML report
python langflow_run_load_test.py --headless --users 25 --duration 120 --html detailed_report.html

# Combined CSV + HTML reporting
python langflow_run_load_test.py --headless --users 100 --duration 300 --csv data --html analysis.html --shape ramp100

# Quick test with report
python langflow_setup_test.py --flow "Memory Chatbot"
python langflow_run_load_test.py --headless --users 10 --duration 60 --html quick_test.html
```
