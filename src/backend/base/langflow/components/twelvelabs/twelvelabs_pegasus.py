# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput, MessageInput
from langflow.io import Output
# from langflow.schema import Data  # Remove this since we're not using Data anymore
from langflow.schema.message import Message
from typing import Dict, Any
from twelvelabs import TwelveLabs
import time
import os
import subprocess
import json
import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class TwelveLabsPegasus(Component):
    display_name = "Twelve Labs Pegasus"
    description = "Chat with videos using Twelve Labs Pegasus API."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "video"
    name = "TwelveLabsPegasus"

    inputs = [
        DataInput(
            name="videodata", 
            display_name="Video Data", 
            info="Video Data",
            is_list=True
        ),
        SecretStrInput(
            name="api_key",
            display_name="Twelve Labs API Key",
            info="Enter your Twelve Labs API Key."
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="Message to chat with the video.",
            required=False,
        )
    ]

    outputs = [
        Output(
            display_name="Message",
            name="response",
            method="process_video",
            type_=Message,
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._video_id = None
        self._index_id = None
        self._task_id = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def _make_api_request(self, client, method, *args, **kwargs):
        """Make API request with retry logic"""
        try:
            return await method(*args, **kwargs)
        except Exception as e:
            self.log(f"API request failed: {str(e)}", "ERROR")
            raise

    def wait_for_task_completion(
        self, 
        client: TwelveLabs, 
        task_id: str, 
        max_retries: int = 120,  # Increased from 60 to 120
        sleep_time: int = 5
    ) -> Dict[str, Any]:
        """Wait for task completion with timeout and improved error handling"""
        retries = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while retries < max_retries:
            try:
                self.log("Checking task status (attempt {})".format(retries + 1))
                result = client.task.retrieve(id=task_id)
                consecutive_errors = 0  # Reset error counter on success
                
                if result.status == "ready":
                    self.log("Task completed successfully!")
                    return result
                elif result.status == "failed":
                    error_msg = f"Task failed with status: {result.status}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                elif result.status == "error":
                    error_msg = f"Task encountered an error: {getattr(result, 'error', 'Unknown error')}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                
                time.sleep(sleep_time)
                retries += 1
                status_msg = f"Processing video... {retries * sleep_time}s elapsed"
                self.status = status_msg
                self.log(status_msg)
                
            except Exception as e:
                consecutive_errors += 1
                error_msg = f"Error checking task status: {str(e)}"
                self.log(error_msg, "WARNING")
                
                if consecutive_errors >= max_consecutive_errors:
                    raise Exception(f"Too many consecutive errors: {error_msg}")
                
                # Wait before retrying after an error
                time.sleep(sleep_time * 2)
                continue
        
        timeout_msg = f"Timeout after {max_retries * sleep_time} seconds"
        self.log(timeout_msg, "ERROR")
        raise Exception(timeout_msg)

    def validate_video_file(self, filepath: str) -> tuple[bool, str]:
        """
        Validate video file using ffprobe.
        Returns (is_valid, error_message)
        """
        try:
            cmd = [
                'ffprobe',
                '-loglevel', 'error',
                '-show_entries', 'stream=codec_type,codec_name',
                '-of', 'default=nw=1',
                '-print_format', 'json',
                '-show_format',
                filepath
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, f"FFprobe error: {result.stderr}"
            
            probe_data = json.loads(result.stdout)
            
            # Check if we have a video stream
            has_video = any(
                stream.get('codec_type') == 'video' 
                for stream in probe_data.get('streams', [])
            )
            
            if not has_video:
                return False, "No video stream found in file"
                
            self.log(f"Video validation successful: {json.dumps(probe_data, indent=2)}")
            return True, ""
            
        except subprocess.SubprocessError as e:
            return False, f"FFprobe process error: {str(e)}"
        except json.JSONDecodeError as e:
            return False, f"FFprobe output parsing error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def on_task_update(self, task):
        """Callback for task status updates"""
        self.status = f"Processing video... Status: {task.status}"
        self.log(self.status)

    def process_video(self) -> Message:
        """Process video using Pegasus and generate response if message is provided"""
        try:
            # If we have a message and already processed video, use existing video_id
            if self.message and self._video_id:
                client = TwelveLabs(api_key=self.api_key)
                response = client.generate.text(
                    video_id=self._video_id,
                    prompt=self.message.text
                )
                return Message(text=response.data)

            # Otherwise process new video
            if not self.videodata or not isinstance(self.videodata, list) or len(self.videodata) != 1:
                return Message(text="Please provide exactly one video")

            video_path = self.videodata[0].data.get('path')
            if not video_path or not os.path.exists(video_path):
                return Message(text="Invalid video path")

            if not self.api_key:
                return Message(text="No API key provided")

            client = TwelveLabs(api_key=self.api_key)

            # Create index and process video
            index = client.index.create(
                name=f"index_{int(time.time())}",
                models=[{"type": "visual", "name": "pegasus1.2", "options": ["visual"]}]
            )
            self._index_id = index.id

            with open(video_path, 'rb') as video_file:
                task = client.task.create(
                    index_id=index.id,
                    file=video_file
                )
            self._task_id = task.id

            # Wait for processing to complete
            task.wait_for_done(sleep_interval=5, callback=self.on_task_update)
            
            if task.status != "ready":
                return Message(text=f"Processing failed with status {task.status}")

            # Store video_id for future use
            self._video_id = task.video_id

            # Generate response if message provided
            if self.message:
                self.status = f"Processing query: {self.message.text}"
                self.log(self.status)

                response = client.generate.text(
                    video_id=self._video_id,
                    prompt=self.message.text
                )
                return Message(text=response.data)
            else:
                return Message(text="Video processed successfully. You can now ask questions about the video.")

        except Exception as e:
            self.log(f"Error: {str(e)}", "ERROR")
            # Clear stored IDs on error
            self._video_id = None
            self._index_id = None
            self._task_id = None
            return Message(text=f"Error: {str(e)}")
