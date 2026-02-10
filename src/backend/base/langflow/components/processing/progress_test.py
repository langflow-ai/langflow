"""Test component for progress bar functionality."""

import time

from lfx.custom import Component
from lfx.io import IntInput, Output
from lfx.schema.data import Data


class ProgressTestComponent(Component):
    """Test component to demonstrate progress bar functionality.
    
    This component simulates a long-running task with progress updates."""

    display_name = "Progress Test"
    description = "Test component that simulates a long-running task with progress."
    icon = "loader"
    name = "ProgressTest"

    inputs = [
        IntInput(
            name="num_steps",
            display_name="Number of Steps",
            info="Number of steps to simulate.",
            value=10,
        ),
        IntInput(
            name="delay_ms",
            display_name="Delay (ms)",
            info="Delay between steps in milliseconds.",
            value=500,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="run_test",
        ),
    ]

    def run_test(self) -> Data:
        """Run test loop with progress updates."""
        total_steps = self.num_steps
        delay_seconds = self.delay_ms / 1000

        steps_completed = []

        for step in range(1, total_steps + 1):
            # Send progress update to frontend
            self.set_progress(step, total_steps, f"Step {step}/{total_steps}")
            self.log(f"Step {step}/{total_steps}")

            # Simulate work
            time.sleep(delay_seconds)

            steps_completed.append(step)

        return Data(
            data={
                "completed_steps": total_steps,
                "status": "done",
                "steps": steps_completed,
                "total_time_seconds": total_steps * delay_seconds
            }
        )
