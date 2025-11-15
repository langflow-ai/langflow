# Flaky Test Detection

This directory contains tools for detecting flaky and unstable tests in the Langflow project.

## Files

- `test_flaky_detection.py` - Main script for running flaky test detection
- `test_results.json` - Example output from a test run
- `README.md` - This documentation file

## Usage

### Basic Usage

Run the flaky test detection with default settings (10 runs):

```bash
cd scripts/flaky_test_detection
uv run python test_flaky_detection.py
```

### Advanced Usage

```bash
# Run with more iterations for better accuracy
uv run python test_flaky_detection.py --runs 20

# Enable verbose output to see detailed progress
uv run python test_flaky_detection.py --runs 15 --verbose

# Save results to a specific file
uv run python test_flaky_detection.py --runs 10 --output my_results.json

# Use custom timeout (in seconds)
uv run python test_flaky_detection.py --runs 10 --timeout 300

# Adjust flaky test threshold (default 0.1 = 10% failure rate)
uv run python test_flaky_detection.py --runs 10 --threshold 0.2

# run tests and save results to a specific file
uv run python scripts/flaky_test_detection/test_flaky_detection.py --runs 10 --output my_results.json
```

### Command Line Options

- `--runs, -n`: Number of test runs (default: 10)
- `--verbose, -v`: Show detailed output
- `--timeout, -t`: Timeout for each test run in seconds (default: 600)
- `--output, -o`: Output results to JSON file
- `--threshold`: Failure threshold for flaky tests (default: 0.1)

## Test Classification

The script classifies tests into four categories:

1. **✅ STABLE**: Test consistently passes (0% failure rate)
2. **🔄 FLAKY**: Test passes sometimes, fails sometimes (failure rate between threshold and 90%)
3. **⚠️ UNSTABLE**: Test fails frequently but not always (failure rate ≥ threshold but < 100%)
4. **❌ CONSISTENTLY FAILING**: Test always fails (100% failure rate)

## Output

The script provides:

- **Summary statistics**: Total runs, pass/fail counts, failure rate
- **Timing analysis**: Average, min, max execution times with variance
- **Failure patterns**: Consecutive failure streaks and common error messages
- **Recommendations**: Specific actions based on test behavior

## Example Output

```
============================================================
FLAKY TEST DETECTION SUMMARY
============================================================
Total runs:      10
Passed runs:     7
Failed runs:     3
Failure rate:    30.0%

Timing Statistics:
Average duration: 45.32s
Min duration:     42.15s
Max duration:     48.91s
Std deviation:    2.18s
Variation coeff:  0.05

Test Classification:
🔄 FLAKY: Test passes sometimes, fails sometimes

Failure Patterns:
Max consecutive failures: 2
Failure streaks: [1, 2]

Common Error Messages:
  2x: FAILED tests/unit/test_example.py::test_flaky - AssertionError
  1x: FAILED tests/unit/test_example.py::test_timeout - TimeoutError

Recommendations:
- Investigate race conditions and timing issues
- Check for dependency on external resources
- Review test isolation and cleanup
```

## Integration with Make

You can run this from the project root using the existing Makefile structure:

```bash
# From project root
make unit_tests  # Run tests normally
uv run python scripts/flaky_test_detection/test_flaky_detection.py  # Run flaky detection
```

## Best Practices

1. **Run multiple iterations**: Use at least 10 runs for meaningful results
2. **Monitor timing**: High variation in execution time may indicate instability
3. **Investigate flaky tests immediately**: They can mask real issues and reduce CI reliability
4. **Use appropriate timeouts**: Balance between catching slow tests and avoiding false failures
5. **Regular monitoring**: Run flaky detection periodically, especially after major changes