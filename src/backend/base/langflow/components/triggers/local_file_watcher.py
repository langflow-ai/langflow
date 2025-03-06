import json
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

import anyio
from loguru import logger

from langflow.base.triggers import BaseTriggerComponent
from langflow.io import IntInput, MessageTextInput
from langflow.schema.data import Data
from langflow.services.triggers.base_trigger import BaseTrigger


class LocalFileWatcherTrigger(BaseTrigger):
    """Local file watcher trigger implementation.

    Checks if a given file has been updated since the last check.
    """

    event_type: ClassVar[str] = "local_file_updated"

    def __init__(self, file_path: str, poll_interval: int = 300, threshold_minutes: int = 5):
        self.file_path = file_path
        self.poll_interval = poll_interval
        self.threshold_minutes = threshold_minutes

    @classmethod
    def from_component_data(cls, component_data: dict[str, Any]):
        file_path = component_data.get("file_path", "")
        poll_interval = component_data.get("poll_interval", 300)
        threshold_minutes = component_data.get("threshold_minutes", 5)
        return cls(file_path=file_path, poll_interval=poll_interval, threshold_minutes=threshold_minutes)

    def initial_state(self) -> str:
        """Return the initial state for this trigger.

        The state stores the last checked time.
        """
        now = datetime.now(timezone.utc)
        state = {
            "last_checked": now.isoformat(),
            "file_modified_at": None,
            "file_path": self.file_path,
            "poll_interval": self.poll_interval,
            "threshold_minutes": self.threshold_minutes,
        }
        return json.dumps(state)

    @classmethod
    async def check_events(cls, subscription: Any) -> list[dict[str, Any]]:
        """Check if the file has been updated since the last check.

        If the file's modification time is more recent than the last_checked time in the subscription state
        and within the threshold, then an event is generated.
        """
        events = []
        try:
            state = json.loads(subscription.state)
            last_checked_str = state.get("last_checked")
            if "file_path" not in state:
                msg = "File path not found in state"
                raise ValueError(msg)

            file_path = state["file_path"]
            if last_checked_str:
                last_checked = datetime.fromisoformat(last_checked_str)
            else:
                last_checked = datetime.now(timezone.utc) - timedelta(seconds=cls.poll_interval)  # fallback

            now = datetime.now(timezone.utc)

            # Get file's last modified time using anyio.Path for async operations
            try:
                path = anyio.Path(file_path)
                stat = await path.stat()
                file_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            except (FileNotFoundError, OSError) as e:
                logger.error(f"Error getting file modification time: {e}")
                file_modified_at = None
            # Check if the file was modified since the last check without applying a time threshold.
            if file_modified_at and file_modified_at > last_checked:
                content = await anyio.Path(file_path).read_text()
                events.append(
                    {
                        "trigger_data": {
                            "file_path": file_path,
                            "file_modified_at": file_modified_at.isoformat(),
                            "content": content,
                        }
                    }
                )

            # Update state
            state["last_checked"] = now.isoformat()
            if file_modified_at:
                state["file_modified_at"] = file_modified_at.isoformat()
            subscription.state = json.dumps(state)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error checking local file events: {e}")
            return []
        return events


class LocalFileWatcherTriggerComponent(BaseTriggerComponent):
    """Component that watches a local file for updates."""

    display_name = "Local File Watcher"
    description = "Triggers a flow when a local file is updated."
    icon = "file"

    inputs = [
        *BaseTriggerComponent._base_inputs,
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Path to the local file to watch for updates.",
            required=True,
        ),
        IntInput(
            name="poll_interval",
            display_name="Poll Interval",
            info="How often (in seconds) to check the file for updates.",
            value=300,
            required=False,
        ),
        IntInput(
            name="threshold_minutes",
            display_name="Threshold Minutes",
            info="The time window in minutes within which a file update is considered. (default: 5 minutes)",
            value=5,
            required=False,
        ),
    ]

    def get_trigger_info(self) -> Data:
        """Get information about this local file watcher trigger for the flow editor.

        Returns:
            Data: A data object containing trigger configuration and parameters.
        """
        trigger_info = {
            "type": "local_file_watcher",
            "file_path": self.file_path,
            "poll_interval": self.poll_interval,
            "threshold_minutes": getattr(self, "threshold_minutes", 5),
        }

        # If testing mode is enabled and mock data is provided, include it
        if hasattr(self, "trigger_content") and self.trigger_content:
            trigger_info.update(
                {
                    "trigger_data": self.trigger_content,
                }
            )

        return Data(data=trigger_info)

    def get_trigger_instance(self):
        """Get the trigger instance for this component."""
        return LocalFileWatcherTrigger(
            file_path=self.file_path,
            poll_interval=self.poll_interval,
            threshold_minutes=getattr(self, "threshold_minutes", 5),
        )
