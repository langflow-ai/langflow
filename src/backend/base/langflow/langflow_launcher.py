import os
import platform
import sys


def main():
    """Launches langflow with appropriate environment setup.

    On macOS, sets required environment variables and replaces current process.
    On other platforms, calls main function directly.
    """
    if platform.system() == "Darwin":  # macOS
        _launch_with_exec()
    else:
        # On non-macOS systems, call the main function directly
        # If no command specified, default to 'run'
        if len(sys.argv) == 1:
            sys.argv.append("run")

        from langflow.__main__ import main as langflow_main

        langflow_main()


def _launch_with_exec():
    """Launch langflow by replacing current process with properly configured environment.

    This approach is necessary because Objective-C libraries are preloaded by the Python
    runtime before any Python code executes. Setting OBJC_DISABLE_INITIALIZE_FORK_SAFETY
    within Python code is too late - it must be set in the parent process environment
    before spawning Python.

    Testing with OBJC_PRINT_INITIALIZE=YES confirms that NSCheapMutableString and
    other Objective-C classes are initialized during Python startup, before any
    user code runs. This causes fork safety issues when gunicorn or multiprocessing
    attempts to fork the process.

    The exec approach sets the environment variables and then replaces the current
    process with a new Python process. This is more efficient than subprocess since
    we don't need the launcher process to remain running, and signals are handled
    directly by the target process.
    """
    # Set environment variables before exec
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    # Additional fix for gunicorn compatibility
    os.environ["no_proxy"] = "*"

    # If no command specified, default to 'run'
    if len(sys.argv) == 1:
        sys.argv.append("run")

    try:
        os.execv(sys.executable, [sys.executable, "-m", "langflow.__main__"] + sys.argv[1:])
    except OSError as e:
        # If exec fails, we need to exit since the process replacement failed
        print(f"Failed to exec langflow: {e}", file=sys.stderr)
        sys.exit(1)
