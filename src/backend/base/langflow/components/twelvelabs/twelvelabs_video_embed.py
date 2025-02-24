# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput, MessageInput
from langflow.io import Output
from langflow.schema import Data
from typing import Dict, Any
from twelvelabs import TwelveLabs
import time
import os
import subprocess
import json

class TwelveLabsVideoEmbeddings(Component):
    display_name = "Twelve Labs Video Embeddings"
    description = "Converts video content to embeddings using Twelve Labs API."
    documentation: str = "https://docs.langflow.org/"
    icon = "video"
    name = "TwelveLabsVideoEmbeddings"

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
        )
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="generate_embeddings"),
    ]

    def wait_for_task_completion(
        self, 
        client: TwelveLabs, 
        task_id: str, 
        max_retries: int = 60, 
        sleep_time: int = 5
    ) -> Dict[str, Any]:
        """Wait for task completion with timeout.
        
        Args:
            client: TwelveLabs client instance
            task_id: ID of the task to monitor
            max_retries: Maximum number of retry attempts
            sleep_time: Time to wait between retries in seconds
            
        Returns:
            Dict containing the task result
            
        Raises:
            Exception: If task fails or times out
        """
        retries = 0
        while retries < max_retries:
            try:
                self.log("Checking task status (attempt {})".format(retries + 1))
                result = client.embed.task.retrieve(id=task_id)
                
                if result.status == "ready":
                    self.log("Task completed successfully!")
                    return result
                elif result.status == "failed":
                    error_msg = f"Task failed with status: {result.status}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                
                time.sleep(sleep_time)
                retries += 1
                status_msg = f"Processing video... {retries * sleep_time}s elapsed"
                self.status = status_msg
                self.log(status_msg)
                
            except Exception as e:
                error_msg = f"Error checking task status: {str(e)}"
                self.log(error_msg, "ERROR")
                raise Exception(error_msg)
        
        timeout_msg = f"Timeout after {max_retries * sleep_time} seconds"
        self.log(timeout_msg, "ERROR")
        raise Exception(timeout_msg)

    def validate_video_file(self, filepath: str) -> tuple[bool, str]:
        """Validate video file using ffprobe."""
        try:
            result = subprocess.run([
                'ffprobe', '-loglevel', 'error',
                '-show_entries', 'stream=codec_type',
                '-of', 'json', filepath
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, f"FFprobe error: {result.stderr}"
            
            probe_data = json.loads(result.stdout)
            has_video = any(
                stream.get('codec_type') == 'video' 
                for stream in probe_data.get('streams', [])
            )
            
            return (True, "") if has_video else (False, "No video stream found")
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def generate_embeddings(self) -> Data:
        try:
            if not self.videodata or not isinstance(self.videodata, list):
                return Data(value={"error": "Invalid video data format"})
            if not self.api_key:
                return Data(value={"error": "No API key provided"})

            client = TwelveLabs(api_key=self.api_key)
            all_embeddings = []
            all_tasks = []  # Track all task IDs
            
            for video_data in self.videodata:
                if not hasattr(video_data, 'data') or 'path' not in video_data.data:
                    self.log("Skipping: No video path found", "ERROR")
                    continue

                video_path = video_data.data['path']
                if not os.path.exists(video_path):
                    self.log(f"Skipping: File not found - {video_path}", "ERROR")
                    continue

                is_valid, error = self.validate_video_file(video_path)
                if not is_valid:
                    self.log(f"Skipping: Invalid video - {error}", "ERROR")
                    continue

                with open(video_path, 'rb') as video_file:
                    task = client.embed.task.create(
                        model_name="Marengo-retrieval-2.7",
                        video_file=video_file,
                        video_embedding_scopes=["clip", "video"]
                    )
                    all_tasks.append(task.id)  # Store task ID

                result = self.wait_for_task_completion(client, task.id)
                
                if not result.video_embedding or not result.video_embedding.segments:
                    self.log(f"No embeddings found for {video_path}", "ERROR")
                    continue
                
                video_embedding = {
                    'task_id': task.id,
                    'file_path': video_path,
                    'video_embedding': None,
                    'clip_embeddings': []
                }

                # Process video-level embedding
                video_segments = [seg for seg in result.video_embedding.segments 
                                if seg.embedding_scope == "video"]
                if video_segments:
                    video_embedding['video_embedding'] = [
                        float(x) for x in video_segments[0].embeddings_float
                    ]

                # Process clip-level embeddings
                clip_segments = [seg for seg in result.video_embedding.segments 
                               if seg.embedding_scope == "clip"]
                if clip_segments:
                    video_embedding['clip_embeddings'] = [
                        [float(x) for x in seg.embeddings_float]
                        for seg in clip_segments
                    ]

                all_embeddings.append(video_embedding)
                self.log(f"Processed {video_path}: {len(video_embedding['clip_embeddings'])} clips")

            if not all_embeddings:
                return Data(value={"error": "No valid embeddings generated"})

            self.status = f"Processed {len(all_embeddings)} videos"
            return Data(value={
                "embeddings": all_embeddings,
                "tasks": all_tasks  # Include task IDs in output
            })
            
        except Exception as e:
            self.status = f"Error: {str(e)}"
            return Data(value={"error": str(e)})
