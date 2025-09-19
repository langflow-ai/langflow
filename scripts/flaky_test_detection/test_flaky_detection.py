#!/usr/bin/env python3
"""Flaky Test Detection Script.

This script runs unit tests multiple times to identify flaky and unstable tests.
It tracks test execution times, failures, and provides detailed reports.

Usage:
    uv run python test_flaky_detection.py [options]

Options:
    --runs N            Number of test runs (default: 10)
    --verbose          Show detailed output
    --timeout SECONDS  Timeout for each test run (default: 600)
    --output FILE      Output results to JSON file
    --threshold RATIO  Failure threshold for flaky tests (default: 0.1)
"""

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


class TestResult:
    """Represents the result of a single test run."""

    def __init__(self, run_number: int, exit_code: int, duration: float, stdout: str, stderr: str):
        self.run_number = run_number
        self.exit_code = exit_code
        self.duration = duration
        self.stdout = stdout
        self.stderr = stderr
        self.passed = exit_code == 0

    def to_dict(self) -> dict:
        return {
            "run_number": self.run_number,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "passed": self.passed,
            "stdout_lines": len(self.stdout.split("\n")) if self.stdout else 0,
            "stderr_lines": len(self.stderr.split("\n")) if self.stderr else 0,
        }


class TestAnalyzer:
    """Analyzes test results to identify flaky tests."""

    def __init__(self, threshold: float = 0.1):
        self.threshold = threshold
        self.results: list[TestResult] = []

    def add_result(self, result: TestResult):
        self.results.append(result)

    def analyze(self) -> dict:
        """Analyze results and return comprehensive report."""
        if not self.results:
            return {"error": "No test results to analyze"}

        total_runs = len(self.results)
        passed_runs = sum(1 for r in self.results if r.passed)
        failed_runs = total_runs - passed_runs

        durations = [r.duration for r in self.results]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)

        # Calculate duration variance
        duration_variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
        duration_std = duration_variance**0.5

        failure_rate = failed_runs / total_runs
        is_flaky = 0 < failure_rate < (1 - self.threshold)
        is_unstable = failure_rate >= self.threshold and failure_rate < 1.0
        is_consistently_failing = failure_rate == 1.0

        # Analyze failure patterns
        failure_patterns = self._analyze_failure_patterns()

        return {
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "failed_runs": failed_runs,
            "failure_rate": failure_rate,
            "is_flaky": is_flaky,
            "is_unstable": is_unstable,
            "is_consistently_failing": is_consistently_failing,
            "duration_stats": {
                "average": avg_duration,
                "min": min_duration,
                "max": max_duration,
                "std_deviation": duration_std,
                "coefficient_of_variation": duration_std / avg_duration if avg_duration > 0 else 0,
            },
            "failure_patterns": failure_patterns,
            "runs": [r.to_dict() for r in self.results],
        }

    def _analyze_failure_patterns(self) -> dict:
        """Analyze patterns in test failures."""
        consecutive_failures = []
        current_streak = 0

        for result in self.results:
            if not result.passed:
                current_streak += 1
            else:
                if current_streak > 0:
                    consecutive_failures.append(current_streak)
                current_streak = 0

        if current_streak > 0:
            consecutive_failures.append(current_streak)

        # Analyze error messages
        error_patterns = defaultdict(int)
        for result in self.results:
            if not result.passed and result.stderr:
                # Extract common error patterns
                for line in result.stderr.split("\n"):
                    if "Error:" in line or "Exception:" in line or "FAILED" in line:
                        # Normalize the error message
                        normalized = re.sub(r"line \d+", "line XXX", line)
                        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD", normalized)
                        error_patterns[normalized[:100]] += 1  # Truncate long messages

        return {
            "consecutive_failures": consecutive_failures,
            "max_consecutive_failures": max(consecutive_failures) if consecutive_failures else 0,
            "common_errors": dict(sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]),
        }


class FlakyTestDetector:
    """Main class for detecting flaky tests."""

    def __init__(self, runs: int = 10, *, verbose: bool = False, timeout: int = 600, threshold: float = 0.1):
        self.runs = runs
        self.verbose = verbose
        self.timeout = timeout
        self.threshold = threshold
        self.analyzer = TestAnalyzer(threshold)

    def run_test_command(self, run_number: int) -> TestResult:
        """Run a single test command and return the result."""
        # Change to project root directory
        project_root = Path(__file__).parent.parent.parent

        command = [
            "uv",
            "run",
            "pytest",
            "src/backend/tests/unit",
            "--ignore=src/backend/tests/integration",
            "--ignore=src/backend/tests/unit/template",
            "--instafail",
            "-ra",
            "-m",
            "not api_key_required",
            "--durations-path",
            "src/backend/tests/.test_durations",
            "--splitting-algorithm",
            "least_duration",
        ]

        if self.verbose:
            print(f"Run {run_number}/{self.runs}: Executing command: {' '.join(command)}")

        start_time = time.time()

        try:
            result = subprocess.run(  # noqa: S603
                command, capture_output=True, text=True, timeout=self.timeout, cwd=project_root, check=False
            )

            duration = time.time() - start_time

            if self.verbose:
                status = "PASSED" if result.returncode == 0 else "FAILED"
                print(f"Run {run_number}/{self.runs}: {status} in {duration:.2f}s")

            return TestResult(
                run_number=run_number,
                exit_code=result.returncode,
                duration=duration,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            if self.verbose:
                print(f"Run {run_number}/{self.runs}: TIMEOUT after {duration:.2f}s")

            return TestResult(
                run_number=run_number,
                exit_code=-1,  # Timeout exit code
                duration=duration,
                stdout="",
                stderr="Test run timed out",
            )

        except Exception as e:  # noqa: BLE001
            duration = time.time() - start_time
            if self.verbose:
                print(f"Run {run_number}/{self.runs}: ERROR - {e!s}")

            return TestResult(
                run_number=run_number,
                exit_code=-2,  # Error exit code
                duration=duration,
                stdout="",
                stderr=f"Error executing test: {e!s}",
            )

    def run_detection(self) -> dict:
        """Run flaky test detection."""
        print(f"Starting flaky test detection with {self.runs} runs")
        print(f"Timeout: {self.timeout}s, Threshold: {self.threshold}")
        print("-" * 60)

        start_time = time.time()

        for run_num in range(1, self.runs + 1):
            result = self.run_test_command(run_num)
            self.analyzer.add_result(result)

            # Show progress
            if not self.verbose:
                status = "✓" if result.passed else "✗"
                print(f"Run {run_num:2d}/{self.runs}: {status} ({result.duration:.1f}s)")

        total_duration = time.time() - start_time

        print("-" * 60)
        print(f"Detection completed in {total_duration:.2f}s")

        analysis = self.analyzer.analyze()
        analysis["meta"] = {
            "total_detection_time": total_duration,
            "runs_requested": self.runs,
            "threshold": self.threshold,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        return analysis

    def print_summary(self, analysis: dict):
        """Print a human-readable summary of the analysis."""
        print("\n" + "=" * 60)
        print("FLAKY TEST DETECTION SUMMARY")
        print("=" * 60)

        if "error" in analysis:
            print(f"Error: {analysis['error']}")
            return

        # Basic stats
        print(f"Total runs:      {analysis['total_runs']}")
        print(f"Passed runs:     {analysis['passed_runs']}")
        print(f"Failed runs:     {analysis['failed_runs']}")
        print(f"Failure rate:    {analysis['failure_rate']:.1%}")

        # Duration stats
        duration = analysis["duration_stats"]
        print("\nTiming Statistics:")
        print(f"Average duration: {duration['average']:.2f}s")
        print(f"Min duration:     {duration['min']:.2f}s")
        print(f"Max duration:     {duration['max']:.2f}s")
        print(f"Std deviation:    {duration['std_deviation']:.2f}s")
        print(f"Variation coeff:  {duration['coefficient_of_variation']:.2f}")

        # Test classification
        print("\nTest Classification:")
        if analysis["is_flaky"]:
            print("🔄 FLAKY: Test passes sometimes, fails sometimes")
        elif analysis["is_unstable"]:
            print("⚠️  UNSTABLE: Test fails frequently but not always")
        elif analysis["is_consistently_failing"]:
            print("❌ CONSISTENTLY FAILING: Test always fails")
        else:
            print("✅ STABLE: Test consistently passes")

        # Failure patterns
        patterns = analysis["failure_patterns"]
        if patterns["consecutive_failures"]:
            print("\nFailure Patterns:")
            print(f"Max consecutive failures: {patterns['max_consecutive_failures']}")
            print(f"Failure streaks: {patterns['consecutive_failures']}")

        if patterns["common_errors"]:
            print("\nCommon Error Messages:")
            for error, count in patterns["common_errors"].items():
                print(f"  {count}x: {error}")

        # Recommendations
        print("\nRecommendations:")
        if analysis["is_flaky"]:
            print("- Investigate race conditions and timing issues")
            print("- Check for dependency on external resources")
            print("- Review test isolation and cleanup")
        elif analysis["is_unstable"]:
            print("- Test has serious reliability issues")
            print("- Consider disabling until issues are resolved")
            print("- Investigate root cause of frequent failures")
        elif analysis["is_consistently_failing"]:
            print("- Test is broken and needs immediate attention")
            print("- Check recent code changes that might have broken the test")
        else:
            print("- Test appears stable and reliable")

        high_variation_threshold = 0.5
        if duration["coefficient_of_variation"] > high_variation_threshold:
            print("- Test execution time varies significantly")
            print("- Consider investigating performance inconsistencies")


def main():
    parser = argparse.ArgumentParser(description="Detect flaky and unstable tests by running them multiple times")

    parser.add_argument("--runs", "-n", type=int, default=10, help="Number of test runs (default: 10)")

    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")

    parser.add_argument(
        "--timeout", "-t", type=int, default=600, help="Timeout for each test run in seconds (default: 600)"
    )

    parser.add_argument("--output", "-o", type=str, help="Output results to JSON file")

    parser.add_argument("--threshold", type=float, default=0.1, help="Failure threshold for flaky tests (default: 0.1)")

    args = parser.parse_args()

    # Validate arguments
    min_runs_required = 2
    if args.runs < min_runs_required:
        print("Error: At least 2 runs are required for meaningful analysis")
        sys.exit(1)

    if args.threshold < 0 or args.threshold > 1:
        print("Error: Threshold must be between 0 and 1")
        sys.exit(1)

    # Run detection
    detector = FlakyTestDetector(runs=args.runs, verbose=args.verbose, timeout=args.timeout, threshold=args.threshold)

    try:
        analysis = detector.run_detection()
        detector.print_summary(analysis)

        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            with output_path.open("w") as f:
                json.dump(analysis, f, indent=2)
            print(f"\nDetailed results saved to: {output_path}")

    except KeyboardInterrupt:
        print("\n\nDetection interrupted by user")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\nError during detection: {e!s}")
        sys.exit(1)


if __name__ == "__main__":
    main()
