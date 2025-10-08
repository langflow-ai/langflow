#!/usr/bin/env python3
"""Example Langflow Load Testing Workflow

This script demonstrates the complete workflow for setting up and running
Langflow load tests with real starter project flows.

Usage:
    python example_workflow.py
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description="", check=True):
    """Run a command with nice output."""
    print(f"\n{'=' * 60}")
    print(f"RUNNING: {description}")
    print(f"{'=' * 60}")
    print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()

    try:
        result = subprocess.run(cmd, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        return False
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return False


def run_command_with_env(cmd, description="", env=None, check=True):
    """Run a command with custom environment variables."""
    print(f"\n{'=' * 60}")
    print(f"RUNNING: {description}")
    print(f"{'=' * 60}")
    print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()

    try:
        result = subprocess.run(cmd, env=env, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        return False
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")

    try:
        import httpx

        print("✅ httpx is available")
    except ImportError:
        print("❌ httpx not found. Install with: pip install httpx")
        return False

    try:
        result = subprocess.run(["locust", "--version"], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ locust is available: {result.stdout.strip()}")
        else:
            print("❌ locust not found. Install with: pip install locust")
            return False
    except FileNotFoundError:
        print("❌ locust not found. Install with: pip install locust")
        return False

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Example Langflow Load Testing Workflow")
    parser.add_argument("--auto", action="store_true", help="Run automatically without user input prompts")
    args = parser.parse_args()

    print("🚀 Langflow Load Testing Example Workflow")
    print("This example will demonstrate the complete load testing setup and execution.")

    # Check dependencies
    if not check_dependencies():
        print("\n❌ Missing dependencies. Please install them and try again.")
        sys.exit(1)

    script_dir = Path(__file__).parent
    setup_script = script_dir / "langflow_setup_test.py"
    runner_script = script_dir / "langflow_run_load_test.py"

    # Check if scripts exist
    if not setup_script.exists():
        print(f"❌ Setup script not found: {setup_script}")
        sys.exit(1)

    if not runner_script.exists():
        print(f"❌ Runner script not found: {runner_script}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("EXAMPLE WORKFLOW STEPS")
    print("=" * 80)
    print("1. List available starter project flows")
    print("2. Set up test environment with a selected flow")
    print("3. Run a quick load test")
    print("4. Show results and cleanup options")
    print("=" * 80)

    def wait_for_user(message):
        if args.auto:
            print(f"\n{message} (auto mode - continuing...)")
            import time

            time.sleep(1)
        else:
            input(f"\n{message}")

    try:
        # Step 1: List available flows
        wait_for_user("Press Enter to list available starter project flows...")
        if not run_command([sys.executable, str(setup_script), "--list-flows"], "List available starter project flows"):
            return

        # Step 2: Setup with Basic Prompting (good for examples)
        wait_for_user("Press Enter to set up test environment with 'Basic Prompting' flow...")
        if not run_command(
            [
                sys.executable,
                str(setup_script),
                "--flow",
                "Basic Prompting",
                "--save-credentials",
                "example_test_creds.json",
            ],
            "Set up test environment",
        ):
            return

        # Step 3: Run a quick load test
        wait_for_user("Press Enter to run a quick load test (10 users, 30 seconds)...")

        # Load credentials from the saved file and set environment variables
        try:
            import json

            with open("example_test_creds.json") as f:
                creds = json.load(f)

            # Set environment variables for the load test
            env = os.environ.copy()
            env["LANGFLOW_HOST"] = creds["host"]
            env["API_KEY"] = creds["api_key"]
            env["FLOW_ID"] = creds["flow_id"]

            print("   🔧 Setting environment variables:")
            print(f"      LANGFLOW_HOST={creds['host']}")
            print(f"      API_KEY={creds['api_key'][:20]}...")
            print(f"      FLOW_ID={creds['flow_id']}")

        except Exception as e:
            print(f"   ⚠️  Could not load credentials: {e}")
            env = os.environ.copy()

        # Run the load test with proper environment
        success = run_command_with_env(
            [
                sys.executable,
                str(runner_script),
                "--headless",
                "--users",
                "100",
                "--spawn-rate",
                "2",
                "--duration",
                "30",
                "--no-start-langflow",
                "--html",
                "langflow_load_test_report.html",
                "--csv",
                "langflow_load_test_results",
            ],
            "Run quick load test with HTML report generation",
            env=env,
        )

        if not success:
            print("⚠️  Load test may have failed, but that's okay for this example")

        # Step 4: Show what's possible
        print(f"\n{'=' * 80}")
        print("EXAMPLE COMPLETE - WHAT'S NEXT?")
        print(f"{'=' * 80}")
        print("The example workflow is complete! Here's what you can do next:")
        print()
        print("🔧 Try different flows:")
        print("   python setup_langflow_test.py --interactive")
        print()
        print("📊 Run more comprehensive tests:")
        print("   python run_load_test.py --shape ramp100 --headless --users 100 --duration 180")
        print()
        print("🌐 Use the web UI for interactive testing:")
        print("   python run_load_test.py")
        print()
        print("💾 Your test credentials are saved in: example_test_creds.json")
        print()
        print("📊 Generated Reports:")
        print("   - langflow_load_test_report.html (detailed HTML report)")
        print("   - langflow_load_test_results_*.csv (CSV data files)")
        print("   - langflow_load_test_detailed_errors_*.log (detailed error logs)")
        print("   - langflow_load_test_error_summary_*.json (error analysis)")
        print("   - langflow_server_logs_during_test_*.log (Langflow server logs)")
        print()
        print("🧹 Clean up:")
        print("   - Remove test flows from Langflow UI")
        print("   - Delete example_test_creds.json")
        print("   - Delete generated report files")
        print("   - Reset environment variables")
        print(f"{'=' * 80}")

        # Cleanup option
        if args.auto:
            print("\nAuto mode - skipping cleanup so you can view the generated reports!")
            print("📁 Files preserved:")
            print("   - example_test_creds.json")
            print("   - langflow_load_test_report.html")
            print("   - langflow_load_test_results_*.csv")
        else:
            cleanup_response = input("\nWould you like to clean up the example files? (y/N): ").strip().lower()

            if cleanup_response == "y":
                files_to_clean = [
                    "example_test_creds.json",
                    "langflow_load_test_report.html",
                    "langflow_load_test_results_failures.csv",
                    "langflow_load_test_results_stats.csv",
                    "langflow_load_test_results_stats_history.csv",
                    "langflow_load_test_results_exceptions.csv",
                ]

                # Also clean up error logs (they have timestamps, so use glob pattern)
                import glob

                error_files = glob.glob("langflow_load_test_detailed_errors_*.log")
                error_files.extend(glob.glob("langflow_load_test_error_summary_*.json"))
                error_files.extend(glob.glob("langflow_server_logs_during_test_*.log"))
                files_to_clean.extend(error_files)

                for file_path in files_to_clean:
                    try:
                        os.remove(file_path)
                        print(f"✅ Cleaned up {file_path}")
                    except FileNotFoundError:
                        pass  # File doesn't exist, that's fine
                    except Exception as e:
                        print(f"⚠️  Could not clean up {file_path}: {e}")

        print("\n🎉 Example workflow completed successfully!")
        print("You're now ready to use Langflow load testing for your own projects.")
        print()
        print("📊 View your load test results:")
        print("   • Open langflow_load_test_report.html in your browser for detailed analysis")
        print("   • Check langflow_load_test_results_*.csv for raw data")
        print("   • Review langflow_load_test_detailed_errors_*.log for comprehensive error details")
        print("   • Analyze langflow_load_test_error_summary_*.json for error patterns")
        print("   • Examine langflow_server_logs_during_test_*.log for server-side issues")

    except KeyboardInterrupt:
        print("\n\n⚠️  Example workflow interrupted by user")
    except Exception as e:
        print(f"\n❌ Example workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
