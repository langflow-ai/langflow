#!/usr/bin/env python3
"""Langflow Load Test Runner

This script provides an easy way to run Langflow load tests.
For first-time setup, use setup_langflow_test.py to create test credentials.

Usage:
    # First time setup (run once):
    python setup_langflow_test.py --interactive

    # Then run load tests:
    python run_load_test.py --help
    python run_load_test.py --users 10 --duration 60
    python run_load_test.py --shape ramp100 --host http://localhost:7860
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, check=True, capture_output=False):
    """Run a shell command with proper error handling."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, check=check)
            return result.stdout.strip()
        subprocess.run(cmd, shell=isinstance(cmd, str), check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        if capture_output and e.stdout:
            print(f"STDOUT: {e.stdout}")
        if capture_output and e.stderr:
            print(f"STDERR: {e.stderr}")
        if check:
            sys.exit(1)


def check_langflow_running(host):
    """Check if Langflow is already running."""
    try:
        import httpx

        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{host}/health")
            return response.status_code == 200
    except Exception:
        return False


def wait_for_langflow(host, timeout=60):
    """Wait for Langflow to be ready."""
    print(f"Waiting for Langflow to be ready at {host}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if check_langflow_running(host):
            print("✅ Langflow is ready!")
            return True
        time.sleep(2)

    print(f"❌ Langflow did not start within {timeout} seconds")
    return False


def start_langflow(host, port):
    """Start Langflow server if not already running."""
    if check_langflow_running(host):
        print(f"✅ Langflow is already running at {host}")
        return None

    print(f"Starting Langflow server on port {port}...")

    # Start Langflow in the background
    cmd = [
        sys.executable,
        "-m",
        "langflow",
        "run",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--auto-login",
        "--log-level",
        "warning",
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for it to be ready
    if wait_for_langflow(host, timeout=60):
        return process
    process.terminate()
    return None


def run_locust_test(args):
    """Run the Locust load test."""
    locust_file = Path(__file__).parent / "langflow_locustfile.py"

    # Check for required environment variables
    if not os.getenv("API_KEY"):
        print("❌ API_KEY environment variable not found!")
        print("Run langflow_setup_test.py first to create test credentials.")
        sys.exit(1)

    if not os.getenv("FLOW_ID"):
        print("❌ FLOW_ID environment variable not found!")
        print("Run langflow_setup_test.py first to create test credentials.")
        sys.exit(1)

    cmd = [
        "locust",
        "-f",
        str(locust_file),
        "--host",
        args.host,
    ]

    # Add shape if specified
    env = os.environ.copy()
    if args.shape:
        env["SHAPE"] = args.shape

    # Add other environment variables
    env["LANGFLOW_HOST"] = args.host

    if args.headless:
        cmd.extend(
            [
                "--headless",
                "--users",
                str(args.users),
                "--spawn-rate",
                str(args.spawn_rate),
                "--run-time",
                f"{args.duration}s",
            ]
        )

    if args.csv:
        cmd.extend(["--csv", args.csv])

    if args.html:
        cmd.extend(["--html", args.html])

    print(f"\n{'=' * 60}")
    print("STARTING LOAD TEST")
    print(f"{'=' * 60}")
    print(f"Command: {' '.join(cmd)}")
    print(f"Host: {args.host}")
    print(f"Users: {args.users}")
    print(f"Duration: {args.duration}s")
    print(f"Shape: {args.shape or 'default'}")
    print(f"API Key: {env.get('API_KEY', 'N/A')[:20]}...")
    print(f"Flow ID: {env.get('FLOW_ID', 'N/A')}")
    if args.html:
        print(f"HTML Report: {args.html}")
    if args.csv:
        print(f"CSV Reports: {args.csv}_*.csv")
    print(f"{'=' * 60}\n")

    subprocess.run(cmd, check=False, env=env)


def main():
    parser = argparse.ArgumentParser(
        description="Run Langflow load tests with automatic setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with web UI (interactive)
  python run_load_test.py

  # Run headless test with 50 users for 2 minutes
  python run_load_test.py --headless --users 50 --duration 120

  # Run with specific load shape
  python run_load_test.py --shape ramp100 --headless --users 100 --duration 180

  # Run against existing Langflow instance
  python run_load_test.py --host http://localhost:8000 --no-start-langflow

  # Save results to CSV
  python run_load_test.py --headless --csv results --users 25 --duration 60
        """,
    )

    # Langflow options
    parser.add_argument(
        "--host", default="http://localhost:7860", help="Langflow host URL (default: http://localhost:7860)"
    )
    parser.add_argument("--port", type=int, default=7860, help="Port to start Langflow on (default: 7860)")
    parser.add_argument(
        "--no-start-langflow",
        action="store_true",
        help="Don't start Langflow automatically (assume it's already running)",
    )

    # Load test options
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no web UI)")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users (default: 10)")
    parser.add_argument(
        "--spawn-rate", type=int, default=2, help="Rate to spawn users at (users per second, default: 2)"
    )
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (default: 60)")
    parser.add_argument("--shape", choices=["ramp100", "stepramp"], help="Load test shape to use")
    parser.add_argument("--csv", help="Save results to CSV files with this prefix")
    parser.add_argument("--html", help="Generate HTML report with this filename (e.g., report.html)")

    args = parser.parse_args()

    # Check dependencies
    try:
        import httpx
        import locust
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install with: pip install locust httpx")
        sys.exit(1)

    langflow_process = None

    try:
        # Start Langflow if needed
        if not args.no_start_langflow:
            langflow_process = start_langflow(args.host, args.port)
            if not langflow_process:
                print("❌ Failed to start Langflow")
                sys.exit(1)
        # Just check if it's running
        elif not check_langflow_running(args.host):
            print(f"❌ Langflow is not running at {args.host}")
            print("Either start Langflow manually or remove --no-start-langflow flag")
            sys.exit(1)

        # Run the load test
        run_locust_test(args)

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        # Clean up Langflow process
        if langflow_process:
            print("\nStopping Langflow server...")
            langflow_process.terminate()
            try:
                langflow_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                langflow_process.kill()
            print("✅ Langflow server stopped")


if __name__ == "__main__":
    main()
