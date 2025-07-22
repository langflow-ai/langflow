import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential
from twelvelabs import TwelveLabs

from lfx.custom import Component
from lfx.inputs import DataInput, DropdownInput, SecretStrInput, StrInput
from lfx.io import Output
from lfx.schema import Data


class TwelveLabsError(Exception):
    """Base exception for Twelve Labs errors."""


class IndexCreationError(TwelveLabsError):
    """Error raised when there's an issue with an index."""


class TaskError(TwelveLabsError):
    """Error raised when a task fails."""


class TaskTimeoutError(TwelveLabsError):
    """Error raised when a task times out."""


class PegasusIndexVideo(Component):
    """Indexes videos using Twelve Labs Pegasus API and adds the video ID to metadata."""

    display_name = "Twelve Labs Pegasus Index Video"
    description = "Index videos using Twelve Labs and add the video_id to metadata."
    icon = "TwelveLabs"
    name = "TwelveLabsPegasusIndexVideo"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    inputs = [
        DataInput(
            name="videodata",
            display_name="Video Data",
            info="Video Data objects (from VideoFile or SplitVideo)",
            is_list=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key", display_name="Twelve Labs API Key", info="Enter your Twelve Labs API Key.", required=True
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Pegasus model to use for indexing",
            options=["pegasus1.2"],
            value="pegasus1.2",
            advanced=False,
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            info="Name of the index to use. If the index doesn't exist, it will be created.",
            required=False,
        ),
        StrInput(
            name="index_id",
            display_name="Index ID",
            info="ID of an existing index to use. If provided, index_name will be ignored.",
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Indexed Data", name="indexed_data", method="index_videos", output_types=["Data"], is_list=True
        ),
    ]

    def _get_or_create_index(self, client: TwelveLabs) -> tuple[str, str]:
        """Get existing index or create new one.

        Returns (index_id, index_name).
        """
        # First check if index_id is provided and valid
        if hasattr(self, "index_id") and self.index_id:
            try:
                index = client.index.retrieve(id=self.index_id)
            except (ValueError, KeyError) as e:
                if not hasattr(self, "index_name") or not self.index_name:
                    error_msg = "Invalid index ID provided and no index name specified for fallback"
                    raise IndexCreationError(error_msg) from e
            else:
                return self.index_id, index.name

        # If index_name is provided, try to find it
        if hasattr(self, "index_name") and self.index_name:
            try:
                # List all indexes and find by name
                indexes = client.index.list()
                for idx in indexes:
                    if idx.name == self.index_name:
                        return idx.id, idx.name

                # If we get here, index wasn't found - create it
                index = client.index.create(
                    name=self.index_name,
                    models=[
                        {
                            "name": self.model_name if hasattr(self, "model_name") else "pegasus1.2",
                            "options": ["visual", "audio"],
                        }
                    ],
                )
            except (ValueError, KeyError) as e:
                error_msg = f"Error with index name {self.index_name}"
                raise IndexCreationError(error_msg) from e
            else:
                return index.id, index.name

        # If we get here, neither index_id nor index_name was provided
        error_msg = "Either index_name or index_id must be provided"
        raise IndexCreationError(error_msg)

    def on_task_update(self, task: Any, video_path: str) -> None:
        """Callback for task status updates.

        Updates the component status with the current task status.
        """
        video_name = Path(video_path).name
        status_msg = f"Indexing {video_name}... Status: {task.status}"
        self.status = status_msg

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=5, max=60), reraise=True)
    def _check_task_status(
        self,
        client: TwelveLabs,
        task_id: str,
        video_path: str,
    ) -> Any:
        """Check task status once.

        Makes a single API call to check the status of a task.
        """
        task = client.task.retrieve(id=task_id)
        self.on_task_update(task, video_path)
        return task

    def _wait_for_task_completion(
        self, client: TwelveLabs, task_id: str, video_path: str, max_retries: int = 120, sleep_time: int = 10
    ) -> Any:
        """Wait for task completion with timeout and improved error handling.

        Polls the task status until completion or timeout.
        """
        retries = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        video_name = Path(video_path).name

        while retries < max_retries:
            try:
                self.status = f"Checking task status for {video_name} (attempt {retries + 1})"
                task = self._check_task_status(client, task_id, video_path)

                if task.status == "ready":
                    self.status = f"Indexing for {video_name} completed successfully!"
                    return task
                if task.status == "failed":
                    error_msg = f"Task failed for {video_name}: {getattr(task, 'error', 'Unknown error')}"
                    self.status = error_msg
                    raise TaskError(error_msg)
                if task.status == "error":
                    error_msg = f"Task encountered an error for {video_name}: {getattr(task, 'error', 'Unknown error')}"
                    self.status = error_msg
                    raise TaskError(error_msg)

                time.sleep(sleep_time)
                retries += 1
                elapsed_time = retries * sleep_time
                self.status = f"Indexing {video_name}... {elapsed_time}s elapsed"

            except (ValueError, KeyError) as e:
                consecutive_errors += 1
                error_msg = f"Error checking task status for {video_name}: {e!s}"
                self.status = error_msg

                if consecutive_errors >= max_consecutive_errors:
                    too_many_errors = f"Too many consecutive errors checking task status for {video_name}"
                    raise TaskError(too_many_errors) from e

                time.sleep(sleep_time * (2**consecutive_errors))
                continue

        timeout_msg = f"Timeout waiting for indexing of {video_name} after {max_retries * sleep_time} seconds"
        self.status = timeout_msg
        raise TaskTimeoutError(timeout_msg)

    def _upload_video(self, client: TwelveLabs, video_path: str, index_id: str) -> str:
        """Upload a single video and return its task ID.

        Uploads a video file to the specified index and returns the task ID.
        """
        video_name = Path(video_path).name
        with Path(video_path).open("rb") as video_file:
            self.status = f"Uploading {video_name} to index {index_id}..."
            task = client.task.create(index_id=index_id, file=video_file)
            task_id = task.id
            self.status = f"Upload complete for {video_name}. Task ID: {task_id}"
            return task_id

    def index_videos(self) -> list[Data]:
        """Indexes each video and adds the video_id to its metadata."""
        if not self.videodata:
            self.status = "No video data provided."
            return []

        if not self.api_key:
            error_msg = "Twelve Labs API Key is required"
            raise IndexCreationError(error_msg)

        if not (hasattr(self, "index_name") and self.index_name) and not (hasattr(self, "index_id") and self.index_id):
            error_msg = "Either index_name or index_id must be provided"
            raise IndexCreationError(error_msg)

        client = TwelveLabs(api_key=self.api_key)
        indexed_data_list: list[Data] = []

        # Get or create the index
        try:
            index_id, index_name = self._get_or_create_index(client)
            self.status = f"Using index: {index_name} (ID: {index_id})"
        except IndexCreationError as e:
            self.status = f"Failed to get/create Twelve Labs index: {e!s}"
            raise

        # First, validate all videos and create a list of valid ones
        valid_videos: list[tuple[Data, str]] = []
        for video_data_item in self.videodata:
            if not isinstance(video_data_item, Data):
                self.status = f"Skipping invalid data item: {video_data_item}"
                continue

            video_info = video_data_item.data
            if not isinstance(video_info, dict):
                self.status = f"Skipping item with invalid data structure: {video_info}"
                continue

            video_path = video_info.get("text")
            if not video_path or not isinstance(video_path, str):
                self.status = f"Skipping item with missing or invalid video path: {video_info}"
                continue

            if not Path(video_path).exists():
                self.status = f"Video file not found, skipping: {video_path}"
                continue

            valid_videos.append((video_data_item, video_path))

        if not valid_videos:
            self.status = "No valid videos to process."
            return []

        # Upload all videos first and collect their task IDs
        upload_tasks: list[tuple[Data, str, str]] = []  # (data_item, video_path, task_id)
        for data_item, video_path in valid_videos:
            try:
                task_id = self._upload_video(client, video_path, index_id)
                upload_tasks.append((data_item, video_path, task_id))
            except (ValueError, KeyError) as e:
                self.status = f"Failed to upload {video_path}: {e!s}"
                continue

        # Now check all tasks in parallel using a thread pool
        with ThreadPoolExecutor(max_workers=min(10, len(upload_tasks))) as executor:
            futures = []
            for data_item, video_path, task_id in upload_tasks:
                future = executor.submit(self._wait_for_task_completion, client, task_id, video_path)
                futures.append((data_item, video_path, future))

            # Process results as they complete
            for data_item, video_path, future in futures:
                try:
                    completed_task = future.result()
                    if completed_task.status == "ready":
                        video_id = completed_task.video_id
                        video_name = Path(video_path).name
                        self.status = f"Video {video_name} indexed successfully. Video ID: {video_id}"

                        # Add video_id to the metadata
                        video_info = data_item.data
                        if "metadata" not in video_info:
                            video_info["metadata"] = {}
                        elif not isinstance(video_info["metadata"], dict):
                            self.status = f"Warning: Overwriting non-dict metadata for {video_path}"
                            video_info["metadata"] = {}

                        video_info["metadata"].update(
                            {"video_id": video_id, "index_id": index_id, "index_name": index_name}
                        )

                        updated_data_item = Data(data=video_info)
                        indexed_data_list.append(updated_data_item)
                except (TaskError, TaskTimeoutError) as e:
                    self.status = f"Failed to process {video_path}: {e!s}"

        if not indexed_data_list:
            self.status = "No videos were successfully indexed."
        else:
            self.status = f"Finished indexing {len(indexed_data_list)}/{len(self.videodata)} videos."

        return indexed_data_list
