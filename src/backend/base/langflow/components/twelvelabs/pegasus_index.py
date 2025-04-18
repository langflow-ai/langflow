from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data
from langflow.field_typing.range_spec import RangeSpec
from typing import Dict, Any, List, Tuple
from twelvelabs import TwelveLabs
import time
import os
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from concurrent.futures import ThreadPoolExecutor

class PegasusIndexVideo(Component):
    """Indexes videos using Twelve Labs Pegasus API and adds the video ID to metadata."""

    display_name = "Pegasus Index Video"
    description = "Index videos using Twelve Labs and add the video_id to metadata."
    icon = "upload-cloud"
    name = "PegasusIndexVideo"

    inputs = [
        DataInput(
            name="videodata", 
            display_name="Video Data", 
            info="Video Data objects (from VideoFile or SplitVideo)",
            is_list=True,
            required=True
        ),
        SecretStrInput(
            name="api_key",
            display_name="Twelve Labs API Key",
            info="Enter your Twelve Labs API Key.",
            required=True
        ),
    ]

    outputs = [
        Output(
            display_name="Indexed Data",
            name="indexed_data",
            method="index_videos",
            output_types=["Data"],
            is_list=True
        ),
    ]

    def on_task_update(self, task, video_path):
        """Callback for task status updates"""
        status_msg = f"Indexing {os.path.basename(video_path)}... Status: {task.status}"
        self.status = status_msg
        self.log(status_msg)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=5, max=60),
        reraise=True
    )
    def _check_task_status(
        self, 
        client: TwelveLabs, 
        task_id: str, 
        video_path: str,
    ) -> Dict[str, Any]:
        """Check task status once"""
        task = client.task.retrieve(id=task_id)
        self.on_task_update(task, video_path)
        return task

    def _wait_for_task_completion(
        self, 
        client: TwelveLabs, 
        task_id: str, 
        video_path: str,
        max_retries: int = 120,
        sleep_time: int = 10
    ) -> Dict[str, Any]:
        """Wait for task completion with timeout and improved error handling"""
        retries = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while retries < max_retries:
            try:
                self.log(f"Checking task status for {os.path.basename(video_path)} (attempt {retries + 1})")
                task = self._check_task_status(client, task_id, video_path)

                if task.status == "ready":
                    self.log(f"Indexing for {os.path.basename(video_path)} completed successfully!")
                    return task
                elif task.status == "failed":
                    error_msg = f"Task failed for {os.path.basename(video_path)}: {getattr(task, 'error', 'Unknown error')}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                elif task.status == "error":
                    error_msg = f"Task encountered an error for {os.path.basename(video_path)}: {getattr(task, 'error', 'Unknown error')}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                
                time.sleep(sleep_time)
                retries += 1
                elapsed_time = retries * sleep_time
                status_msg = f"Indexing {os.path.basename(video_path)}... {elapsed_time}s elapsed"
                self.status = status_msg
                
            except Exception as e:
                consecutive_errors += 1
                error_msg = f"Error checking task status for {os.path.basename(video_path)}: {str(e)}"
                self.log(error_msg, "WARNING")
                
                if consecutive_errors >= max_consecutive_errors:
                    raise Exception(f"Too many consecutive errors checking task status for {os.path.basename(video_path)}: {error_msg}")
                
                time.sleep(sleep_time * (2 ** consecutive_errors))
                continue
        
        timeout_msg = f"Timeout waiting for indexing of {os.path.basename(video_path)} after {max_retries * sleep_time} seconds"
        self.log(timeout_msg, "ERROR")
        raise TimeoutError(timeout_msg)

    def _upload_video(self, client: TwelveLabs, video_path: str, index_id: str) -> str:
        """Upload a single video and return its task ID"""
        with open(video_path, 'rb') as video_file:
            self.log(f"Uploading {os.path.basename(video_path)} to index {index_id}...")
            task = client.task.create(
                index_id=index_id,
                file=video_file,
                language="en"
            )
            task_id = task.id
            self.log(f"Upload complete for {os.path.basename(video_path)}. Task ID: {task_id}")
            return task_id

    def index_videos(self) -> List[Data]:
        """Indexes each video and adds the video_id to its metadata."""
        if not self.videodata:
            self.log("No video data provided.", "WARNING")
            return []
        
        if not self.api_key:
            raise ValueError("Twelve Labs API Key is required.")

        client = TwelveLabs(api_key=self.api_key)
        indexed_data_list = []
        
        # Create a single index for this component run
        try:
            index_name = f"langflow-index-{int(time.time())}"
            self.log(f"Creating index: {index_name}")
            index = client.index.create(
                name=index_name,
                models=[
                    {
                        "name": "pegasus1.2",
                        "options": ["visual","audio"]
                    }
                ]
            )
            index_id = index.id
            self.log(f"Created index {index_name} with ID: {index_id}")
        except Exception as e:
            self.log(f"Failed to create Twelve Labs index: {str(e)}", "ERROR")
            raise

        # First, validate all videos and create a list of valid ones
        valid_videos: List[Tuple[Data, str]] = []
        for video_data_item in self.videodata:
            if not isinstance(video_data_item, Data):
                self.log(f"Skipping invalid data item: {video_data_item}", "WARNING")
                continue

            video_info = video_data_item.data
            if not isinstance(video_info, dict):
                self.log(f"Skipping item with invalid data structure: {video_info}", "WARNING")
                continue

            video_path = video_info.get('text')
            if not video_path or not isinstance(video_path, str):
                self.log(f"Skipping item with missing or invalid video path: {video_info}", "WARNING")
                continue

            if not os.path.exists(video_path):
                self.log(f"Video file not found, skipping: {video_path}", "ERROR")
                continue
            
            valid_videos.append((video_data_item, video_path))

        if not valid_videos:
            self.log("No valid videos to process.", "WARNING")
            return []

        # Upload all videos first and collect their task IDs
        upload_tasks: List[Tuple[Data, str, str]] = []  # (data_item, video_path, task_id)
        for data_item, video_path in valid_videos:
            try:
                task_id = self._upload_video(client, video_path, index_id)
                upload_tasks.append((data_item, video_path, task_id))
            except Exception as e:
                self.log(f"Failed to upload {video_path}: {str(e)}", "ERROR")
                continue

        # Now check all tasks in parallel using a thread pool
        with ThreadPoolExecutor(max_workers=min(10, len(upload_tasks))) as executor:
            futures = []
            for data_item, video_path, task_id in upload_tasks:
                future = executor.submit(
                    self._wait_for_task_completion,
                    client,
                    task_id,
                    video_path
                )
                futures.append((data_item, video_path, future))

            # Process results as they complete
            for data_item, video_path, future in futures:
                try:
                    completed_task = future.result()
                    if completed_task.status == "ready":
                        video_id = completed_task.video_id
                        self.log(f"Video {os.path.basename(video_path)} indexed successfully. Video ID: {video_id}")
                        
                        # Add video_id to the metadata
                        video_info = data_item.data
                        if 'metadata' not in video_info:
                            video_info['metadata'] = {}
                        elif not isinstance(video_info['metadata'], dict):
                            self.log(f"Warning: Overwriting non-dict metadata for {video_path}", "WARNING")
                            video_info['metadata'] = {}

                        video_info['metadata']['video_id'] = video_id
                        video_info['metadata']['index_id'] = index_id
                        
                        updated_data_item = Data(data=video_info)
                        indexed_data_list.append(updated_data_item)
                except Exception as e:
                    self.log(f"Failed to process {video_path}: {str(e)}", "ERROR")

        if not indexed_data_list:
            self.log("No videos were successfully indexed.", "WARNING")
        
        self.status = f"Finished indexing {len(indexed_data_list)}/{len(self.videodata)} videos."
        return indexed_data_list
