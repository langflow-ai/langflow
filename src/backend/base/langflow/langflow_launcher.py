import os
import platform
import signal
import subprocess
import sys


def main():
    """Launches langflow in a subprocess on macOS to set environment variables,
    or directly calls main on other platforms.
    """
    if platform.system() == "Darwin":  # macOS
        _launch_with_subprocess()
    else:
        # On non-macOS systems, call the main function directly
        # If no command specified, default to 'run'
        if len(sys.argv) == 1:
            sys.argv.append("run")

        from langflow.__main__ import main as langflow_main

        langflow_main()


def _launch_with_subprocess():
    """Launch langflow in subprocess with macOS-specific environment variables."""
    env = os.environ.copy()
    # Required for macOS to avoid fork safety issues.
    # Error: """
    # When fork() is called, NSCheapMutableString initialize may be in progress in another thread.
    # This cannot be safely called or ignored in the fork() child process, causing a crash.
    # To debug, set a breakpoint on objc_initializeAfterForkError
    # """
    env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    # If no command specified, default to 'run'
    args = sys.argv[1:] if len(sys.argv) > 1 else ["run"]
    command = ["uv", "run", "python", "-m", "langflow.__main__"] + args

    process: subprocess.Popen | None = None

    def signal_handler(signum: int, frame):
        """Forward signals to the child process."""
        if process and process.poll() is None:
            try:
                process.send_signal(signum)
            except ProcessLookupError:
                # Process already terminated
                pass

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        process = subprocess.Popen(command, env=env)
        return process.wait()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Process didn't terminate gracefully, killing...")
                process.kill()
        return 130  # standard exit code for SIGINT
    except Exception as e:
        print(f"Error running langflow: {e}")
        return 1
