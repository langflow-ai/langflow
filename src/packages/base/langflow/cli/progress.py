import platform
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import click

MIN_DURATION_THRESHOLD = 0.1  # Minimum duration to show in seconds (100ms)


class ProgressIndicator:
    """A CLI progress indicator that shows user-friendly step-by-step progress.

    Shows animated loading indicators (□ → ■) for each step of the initialization process.
    """

    def __init__(self, *, verbose: bool = False):
        self.verbose = verbose
        self.steps: list[dict[str, Any]] = []
        self.current_step = 0
        self.running = False
        self._stop_animation = False
        self._animation_thread: threading.Thread | None = None

        # Use Windows-safe characters on Windows to prevent encoding issues
        if platform.system() == "Windows":
            self._animation_chars = ["-", "\\", "|", "/"]  # ASCII spinner
            self._success_icon = "+"  # ASCII plus sign
            self._failure_icon = "x"  # ASCII x
            self._farewell_emoji = ":)"  # ASCII smiley
        else:
            self._animation_chars = ["□", "▢", "▣", "■"]  # Unicode squares
            self._success_icon = "✓"  # Unicode checkmark
            self._failure_icon = "✗"  # Unicode cross
            self._farewell_emoji = "👋"  # Unicode wave

        self._animation_index = 0

    def add_step(self, title: str, description: str = "") -> None:
        """Add a step to the progress indicator."""
        self.steps.append(
            {
                "title": title,
                "description": description,
                "status": "pending",  # pending, running, completed, failed
                "start_time": None,
                "end_time": None,
            }
        )

    def _animate_step(self, step_index: int) -> None:
        """Animate the current step with rotating square characters."""
        if step_index >= len(self.steps):
            return

        step = self.steps[step_index]

        while self.running and step["status"] == "running" and not self._stop_animation:
            # Clear the current line and move cursor to beginning
            sys.stdout.write("\r")

            # Show the animated character
            animation_char = self._animation_chars[self._animation_index]

            # Print the step with animation
            line = f"{animation_char} {step['title']}..."
            sys.stdout.write(line)
            sys.stdout.flush()

            # Update animation
            self._animation_index = (self._animation_index + 1) % len(self._animation_chars)

            time.sleep(0.15)  # Animation speed

    def start_step(self, step_index: int) -> None:
        """Start a specific step and begin animation."""
        if step_index >= len(self.steps):
            return

        self.current_step = step_index
        step = self.steps[step_index]
        step["status"] = "running"
        step["start_time"] = time.time()

        self.running = True
        self._stop_animation = False

        # Start animation in a separate thread
        self._animation_thread = threading.Thread(target=self._animate_step, args=(step_index,))
        self._animation_thread.daemon = True
        self._animation_thread.start()

    def complete_step(self, step_index: int, *, success: bool = True) -> None:
        """Complete a step and stop its animation."""
        if step_index >= len(self.steps):
            return

        step = self.steps[step_index]
        step["status"] = "completed" if success else "failed"
        step["end_time"] = time.time()

        # Stop animation
        self._stop_animation = True
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=0.5)

        self.running = False

        # Clear the current line and print final result
        sys.stdout.write("\r")

        if success:
            icon = click.style(self._success_icon, fg="green", bold=True)
            title = click.style(step["title"], fg="green")
        else:
            icon = click.style(self._failure_icon, fg="red", bold=True)
            title = click.style(step["title"], fg="red")

        duration = ""
        if step["start_time"] and step["end_time"]:
            elapsed = step["end_time"] - step["start_time"]
            if self.verbose and elapsed > MIN_DURATION_THRESHOLD:  # Only show duration if verbose and > 100ms
                duration = click.style(f" ({elapsed:.2f}s)", fg="bright_black")

        line = f"{icon} {title}{duration}"
        click.echo(line)

    def fail_step(self, step_index: int, error_msg: str = "") -> None:
        """Mark a step as failed."""
        self.complete_step(step_index, success=False)
        if error_msg and self.verbose:
            click.echo(click.style(f"   Error: {error_msg}", fg="red"))

    @contextmanager
    def step(self, step_index: int) -> Generator[None, None, None]:
        """Context manager for running a step with automatic completion."""
        try:
            self.start_step(step_index)
            yield
            self.complete_step(step_index, success=True)
        except Exception as e:
            error_msg = str(e) if self.verbose else ""
            self.fail_step(step_index, error_msg)
            raise

    def print_summary(self) -> None:
        """Print a summary of all completed steps."""
        if not self.verbose:
            return

        completed_steps = [s for s in self.steps if s["status"] in ["completed", "failed"]]
        if not completed_steps:
            return

        total_time = sum(
            (s["end_time"] - s["start_time"]) for s in completed_steps if s["start_time"] and s["end_time"]
        )

        click.echo()
        click.echo(click.style(f"Total initialization time: {total_time:.2f}s", fg="bright_black"))

    def print_shutdown_summary(self) -> None:
        """Print a summary of all completed shutdown steps."""
        if not self.verbose:
            return

        completed_steps = [s for s in self.steps if s["status"] in ["completed", "failed"]]
        if not completed_steps:
            return

        total_time = sum(
            (s["end_time"] - s["start_time"]) for s in completed_steps if s["start_time"] and s["end_time"]
        )

        click.echo()
        click.echo(click.style(f"Total shutdown time: {total_time:.2f}s", fg="bright_black"))


def create_langflow_progress(*, verbose: bool = False) -> ProgressIndicator:
    """Create a progress indicator with predefined Langflow initialization steps."""
    progress = ProgressIndicator(verbose=verbose)

    # Define the initialization steps matching the order in main.py
    steps = [
        ("Initializing Langflow", "Setting up basic configuration"),
        ("Checking Environment", "Loading environment variables and settings"),
        ("Starting Core Services", "Initializing database and core services"),
        ("Connecting Database", "Setting up database connection and migrations"),
        ("Loading Components", "Caching component types and custom components"),
        ("Adding Starter Projects", "Creating or updating starter project templates"),
        ("Launching Langflow", "Starting server and final setup"),
    ]

    for title, description in steps:
        progress.add_step(title, description)

    return progress


def create_langflow_shutdown_progress(*, verbose: bool = False, multiple_workers: bool = False) -> ProgressIndicator:
    """Create a progress indicator with predefined Langflow shutdown steps."""
    progress = ProgressIndicator(verbose=verbose)

    # Define the shutdown steps in reverse order of initialization
    if multiple_workers:
        import os

        steps = [
            (f"[Worker PID {os.getpid()}] Stopping Server", "Gracefully stopping the web server"),
            (
                f"[Worker PID {os.getpid()}] Cancelling Background Tasks",
                "Stopping file synchronization and background jobs",
            ),
            (f"[Worker PID {os.getpid()}] Cleaning Up Services", "Teardown database connections and services"),
            (f"[Worker PID {os.getpid()}] Clearing Temporary Files", "Removing temporary directories and cache"),
            (f"[Worker PID {os.getpid()}] Finalizing Shutdown", "Completing cleanup and logging"),
        ]
    else:
        steps = [
            ("Stopping Server", "Gracefully stopping the web server"),
            ("Cancelling Background Tasks", "Stopping file synchronization and background jobs"),
            ("Cleaning Up Services", "Teardown database connections and services"),
            ("Clearing Temporary Files", "Removing temporary directories and cache"),
            ("Finalizing Shutdown", "Completing cleanup and logging"),
        ]

    for title, description in steps:
        progress.add_step(title, description)

    return progress
