import json
import subprocess
import time
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential
from twelvelabs import TwelveLabs

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs import DataInput, DropdownInput, MessageInput, MultilineInput, SecretStrInput, SliderInput
from lfx.io import Output
from lfx.schema.message import Message


class TaskError(Exception):
    """Error raised when a task fails."""


class TaskTimeoutError(Exception):
    """Error raised when a task times out."""


class IndexCreationError(Exception):
    """Error raised when there's an issue with an index."""


class ApiRequestError(Exception):
    """Error raised when an API request fails."""


class VideoValidationError(Exception):
    """Error raised when video validation fails."""


class TwelveLabsPegasus(Component):
    display_name = "Twelve Labs Pegasus"
    description = "Chat with videos using Twelve Labs Pegasus API."
    icon = "TwelveLabs"
    name = "TwelveLabsPegasus"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    inputs = [
        DataInput(name="videodata", display_name="Video Data", info="Video Data", is_list=True),
        SecretStrInput(
            name="api_key", display_name="Twelve Labs API Key", info="Enter your Twelve Labs API Key.", required=True
        ),
        MessageInput(
            name="video_id",
            display_name="Pegasus Video ID",
            info="Enter a Video ID for a previously indexed video.",
        ),
        MessageInput(
            name="index_name",
            display_name="Index Name",
            info="Name of the index to use. If the index doesn't exist, it will be created.",
            required=False,
        ),
        MessageInput(
            name="index_id",
            display_name="Index ID",
            info="ID of an existing index to use. If provided, index_name will be ignored.",
            required=False,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Pegasus model to use for indexing",
            options=["pegasus1.2"],
            value="pegasus1.2",
            advanced=False,
        ),
        MultilineInput(
            name="message",
            display_name="Prompt",
            info="Message to chat with the video.",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            info=(
                "Controls randomness in responses. Lower values are more deterministic, "
                "higher values are more creative."
            ),
        ),
    ]

    outputs = [
        Output(
            display_name="Message",
            name="response",
            method="process_video",
            type_=Message,
        ),
        Output(
            display_name="Video ID",
            name="processed_video_id",
            method="get_video_id",
            type_=Message,
        ),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._task_id: str | None = None
        self._video_id: str | None = None
        self._index_id: str | None = None
        self._index_name: str | None = None
        self._message: str | None = None

    def _get_or_create_index(self, client: TwelveLabs) -> tuple[str, str]:
        """Get existing index or create new one.

        Returns (index_id, index_name).
        """
        # First check if index_id is provided and valid
        if hasattr(self, "_index_id") and self._index_id:
            try:
                index = client.index.retrieve(id=self._index_id)
                self.log(f"Found existing index with ID: {self._index_id}")
            except (ValueError, KeyError) as e:
                self.log(f"Error retrieving index with ID {self._index_id}: {e!s}", "WARNING")
            else:
                return self._index_id, index.name

        # If index_name is provided, try to find it
        if hasattr(self, "_index_name") and self._index_name:
            try:
                # List all indexes and find by name
                indexes = client.index.list()
                for idx in indexes:
                    if idx.name == self._index_name:
                        self.log(f"Found existing index: {self._index_name} (ID: {idx.id})")
                        return idx.id, idx.name

                # If we get here, index wasn't found - create it
                self.log(f"Creating new index: {self._index_name}")
                index = client.index.create(
                    name=self._index_name,
                    models=[
                        {
                            "name": self.model_name if hasattr(self, "model_name") else "pegasus1.2",
                            "options": ["visual", "audio"],
                        }
                    ],
                )
            except (ValueError, KeyError) as e:
                self.log(f"Error with index name {self._index_name}: {e!s}", "ERROR")
                error_message = f"Error with index name {self._index_name}"
                raise IndexCreationError(error_message) from e
            else:
                return index.id, index.name

        # If neither is provided, create a new index with timestamp
        try:
            index_name = f"index_{int(time.time())}"
            self.log(f"Creating new index: {index_name}")
            index = client.index.create(
                name=index_name,
                models=[
                    {
                        "name": self.model_name if hasattr(self, "model_name") else "pegasus1.2",
                        "options": ["visual", "audio"],
                    }
                ],
            )
        except (ValueError, KeyError) as e:
            self.log(f"Failed to create new index: {e!s}", "ERROR")
            error_message = "Failed to create new index"
            raise IndexCreationError(error_message) from e
        else:
            return index.id, index.name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
    async def _make_api_request(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """Make API request with retry logic.

        Retries failed requests with exponential backoff.
        """
        try:
            return await method(*args, **kwargs)
        except (ValueError, KeyError) as e:
            self.log(f"API request failed: {e!s}", "ERROR")
            error_message = "API request failed"
            raise ApiRequestError(error_message) from e

    def wait_for_task_completion(
        self, client: TwelveLabs, task_id: str, max_retries: int = 120, sleep_time: int = 5
    ) -> Any:
        """Wait for task completion with timeout and improved error handling.

        Polls the task status until completion or timeout.
        """
        retries = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        while retries < max_retries:
            try:
                self.log(f"Checking task status (attempt {retries + 1})")
                result = client.task.retrieve(id=task_id)
                consecutive_errors = 0  # Reset error counter on success

                if result.status == "ready":
                    self.log("Task completed successfully!")
                    return result
                if result.status == "failed":
                    error_msg = f"Task failed with status: {result.status}"
                    self.log(error_msg, "ERROR")
                    raise TaskError(error_msg)
                if result.status == "error":
                    error_msg = f"Task encountered an error: {getattr(result, 'error', 'Unknown error')}"
                    self.log(error_msg, "ERROR")
                    raise TaskError(error_msg)

                time.sleep(sleep_time)
                retries += 1
                status_msg = f"Processing video... {retries * sleep_time}s elapsed"
                self.status = status_msg
                self.log(status_msg)

            except (ValueError, KeyError) as e:
                consecutive_errors += 1
                error_msg = f"Error checking task status: {e!s}"
                self.log(error_msg, "WARNING")

                if consecutive_errors >= max_consecutive_errors:
                    too_many_errors = "Too many consecutive errors"
                    raise TaskError(too_many_errors) from e

                time.sleep(sleep_time * 2)
                continue

        timeout_msg = f"Timeout after {max_retries * sleep_time} seconds"
        self.log(timeout_msg, "ERROR")
        raise TaskTimeoutError(timeout_msg)

    def validate_video_file(self, filepath: str) -> tuple[bool, str]:
        """Validate video file using ffprobe.

        Returns (is_valid, error_message).
        """
        # Ensure filepath is a string and doesn't contain shell metacharacters
        if not isinstance(filepath, str) or any(c in filepath for c in ";&|`$(){}[]<>*?!#~"):
            return False, "Invalid filepath"

        try:
            cmd = [
                "ffprobe",
                "-loglevel",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name",
                "-of",
                "default=nw=1",
                "-print_format",
                "json",
                "-show_format",
                filepath,
            ]

            # Use subprocess with a list of arguments to avoid shell injection
            # We need to skip the S603 warning here as we're taking proper precautions
            # with input validation and using shell=False
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                check=False,
                shell=False,  # Explicitly set shell=False for security
            )

            if result.returncode != 0:
                return False, f"FFprobe error: {result.stderr}"

            probe_data = json.loads(result.stdout)

            has_video = any(stream.get("codec_type") == "video" for stream in probe_data.get("streams", []))

            if not has_video:
                return False, "No video stream found in file"

            self.log(f"Video validation successful: {json.dumps(probe_data, indent=2)}")
        except subprocess.SubprocessError as e:
            return False, f"FFprobe process error: {e!s}"
        except json.JSONDecodeError as e:
            return False, f"FFprobe output parsing error: {e!s}"
        except (ValueError, OSError) as e:
            return False, f"Validation error: {e!s}"
        else:
            return True, ""

    def on_task_update(self, task: Any) -> None:
        """Callback for task status updates.

        Updates the component status with the current task status.
        """
        self.status = f"Processing video... Status: {task.status}"
        self.log(self.status)

    def process_video(self) -> Message:
        """Process video using Pegasus and generate response if message is provided.

        Handles video indexing and question answering using the Twelve Labs API.
        """
        # Check and initialize inputs
        if hasattr(self, "index_id") and self.index_id:
            self._index_id = self.index_id.text if hasattr(self.index_id, "text") else self.index_id

        if hasattr(self, "index_name") and self.index_name:
            self._index_name = self.index_name.text if hasattr(self.index_name, "text") else self.index_name

        if hasattr(self, "video_id") and self.video_id:
            self._video_id = self.video_id.text if hasattr(self.video_id, "text") else self.video_id

        if hasattr(self, "message") and self.message:
            self._message = self.message.text if hasattr(self.message, "text") else self.message

        try:
            # If we have a message and already processed video, use existing video_id
            if self._message and self._video_id and self._video_id != "":
                self.status = f"Have video id: {self._video_id}"

                client = TwelveLabs(api_key=self.api_key)

                self.status = f"Processing query (w/ video ID): {self._video_id} {self._message}"
                self.log(self.status)

                response = client.generate.text(
                    video_id=self._video_id,
                    prompt=self._message,
                    temperature=self.temperature,
                )
                return Message(text=response.data)

            # Otherwise process new video
            if not self.videodata or not isinstance(self.videodata, list) or len(self.videodata) != 1:
                return Message(text="Please provide exactly one video")

            video_path = self.videodata[0].data.get("text")
            if not video_path or not Path(video_path).exists():
                return Message(text="Invalid video path")

            if not self.api_key:
                return Message(text="No API key provided")

            client = TwelveLabs(api_key=self.api_key)

            # Get or create index
            try:
                index_id, index_name = self._get_or_create_index(client)
                self.status = f"Using index: {index_name} (ID: {index_id})"
                self.log(f"Using index: {index_name} (ID: {index_id})")
                self._index_id = index_id
                self._index_name = index_name
            except IndexCreationError as e:
                return Message(text=f"Failed to get/create index: {e}")

            with Path(video_path).open("rb") as video_file:
                task = client.task.create(index_id=self._index_id, file=video_file)
            self._task_id = task.id

            # Wait for processing to complete
            task.wait_for_done(sleep_interval=5, callback=self.on_task_update)

            if task.status != "ready":
                return Message(text=f"Processing failed with status {task.status}")

            # Store video_id for future use
            self._video_id = task.video_id

            # Generate response if message provided
            if self._message:
                self.status = f"Processing query: {self._message}"
                self.log(self.status)

                response = client.generate.text(
                    video_id=self._video_id,
                    prompt=self._message,
                    temperature=self.temperature,
                )
                return Message(text=response.data)

            success_msg = (
                f"Video processed successfully. You can now ask questions about the video. Video ID: {self._video_id}"
            )
            return Message(text=success_msg)

        except (ValueError, KeyError, IndexCreationError, TaskError, TaskTimeoutError) as e:
            self.log(f"Error: {e!s}", "ERROR")
            # Clear stored IDs on error
            self._video_id = None
            self._index_id = None
            self._task_id = None
            return Message(text=f"Error: {e!s}")

    def get_video_id(self) -> Message:
        """Return the video ID of the processed video as a Message.

        Returns an empty string if no video has been processed.
        """
        video_id = self._video_id or ""
        return Message(text=video_id)
