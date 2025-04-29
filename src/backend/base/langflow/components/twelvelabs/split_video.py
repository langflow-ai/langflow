from langflow.custom import Component
from langflow.inputs import BoolInput, IntInput, HandleInput, DropdownInput
from langflow.schema import Data
from langflow.template import Output
import os
import subprocess
from typing import List
from datetime import datetime
import hashlib
import math

class SplitVideoComponent(Component):
    """A component that splits a video into multiple clips of specified duration using FFmpeg."""

    display_name = "Split Video"
    description = "Split a video into multiple clips of specified duration."
    icon = "TwelveLabs"
    name = "SplitVideo"

    inputs = [
        HandleInput(
            name="videodata",
            display_name="Video Data",
            info="Input video data from VideoFile component",
            required=True,
            input_types=["Data"],
        ),
        IntInput(
            name="clip_duration",
            display_name="Clip Duration (seconds)",
            info="Duration of each clip in seconds",
            required=True,
            value=30,
        ),
        DropdownInput(
            name="last_clip_handling",
            display_name="Last Clip Handling",
            info=(
                "How to handle the final clip when it would be shorter than the specified duration:\n"
                "- Truncate: Skip the final clip entirely if it's shorter than the specified duration\n"
                "- Overlap Previous: Start the final clip earlier to maintain full duration, overlapping with previous clip\n"
                "- Keep Short: Keep the final clip at its natural length, even if shorter than specified duration"
            ),
            options=["Truncate", "Overlap Previous", "Keep Short"],
            value="Overlap Previous",
            required=True,
        ),
        BoolInput(
            name="include_original",
            display_name="Include Original Video",
            info="Whether to include the original video in the output",
            value=False,
        ),
    ]

    outputs = [
        Output(
            name="clips",
            display_name="Video Clips",
            method="process",
            output_types=["Data"],
        ),
    ]

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration using FFmpeg."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFprobe error: {result.stderr}")
            return float(result.stdout.strip())
        except Exception as e:
            self.log(f"Error getting video duration: {str(e)}", "ERROR")
            raise

    def get_output_dir(self, video_path: str) -> str:
        """Create a unique output directory for clips based on video name and timestamp."""
        # Get the video filename without extension
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        
        # Create a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Create a unique hash from the video path
        path_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
        
        # Create the output directory path
        output_dir = os.path.join(
            os.path.dirname(video_path),
            f"clips_{base_name}_{timestamp}_{path_hash}"
        )
        
        # Create the directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        return output_dir

    def process_video(self, video_path: str, clip_duration: int, include_original: bool) -> List[Data]:
        """Process video and split it into clips using FFmpeg."""
        try:
            # Get video duration
            total_duration = self.get_video_duration(video_path)
            
            # Calculate number of clips (ceiling to include partial clip)
            num_clips = math.ceil(total_duration / clip_duration)
            self.log(f"Total duration: {total_duration}s, Clip duration: {clip_duration}s, Number of clips: {num_clips}")
            
            # Create output directory for clips
            output_dir = self.get_output_dir(video_path)
            
            # Get original video info
            original_filename = os.path.basename(video_path)
            original_name = os.path.splitext(original_filename)[0]
            
            # List to store all video paths (including original if requested)
            video_paths = []
            
            # Add original video if requested
            if include_original:
                original_data = {
                    "text": video_path,
                    "metadata": {
                        "source": video_path,
                        "type": "video",
                        "clip_index": -1,  # -1 indicates original video
                        "duration": total_duration,
                        "original_video": {
                            "name": original_name,
                            "filename": original_filename,
                            "path": video_path,
                            "duration": total_duration,
                            "total_clips": num_clips,
                            "clip_duration": clip_duration
                        }
                    }
                }
                video_paths.append(Data(data=original_data))
            
            # Split video into clips
            for i in range(num_clips):
                start_time = i * clip_duration
                end_time = min((i + 1) * clip_duration, total_duration)
                duration = end_time - start_time
                
                # Handle last clip if it's shorter
                if i == num_clips - 1 and duration < clip_duration:
                    if self.last_clip_handling == "Truncate":
                        # Skip if the last clip would be too short
                        continue
                    elif self.last_clip_handling == "Overlap Previous" and i > 0:
                        # Start from earlier to make full duration
                        start_time = total_duration - clip_duration
                        duration = clip_duration
                    # For "Keep Short", we use the original start_time and duration
                
                # Skip if duration is too small (less than 1 second)
                if duration < 1:
                    continue
                
                # Generate output path
                output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")
                
                try:
                    # Use FFmpeg to split the video
                    cmd = [
                        'ffmpeg',
                        '-i', video_path,
                        '-ss', str(start_time),
                        '-t', str(duration),
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-y',  # Overwrite output file if it exists
                        output_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"FFmpeg error: {result.stderr}")
                    
                    # Create Data object for the clip
                    clip_data = {
                        "text": output_path,
                        "metadata": {
                            "source": video_path,
                            "type": "video",
                            "clip_index": i,
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": duration,
                            "original_video": {
                                "name": original_name,
                                "filename": original_filename,
                                "path": video_path,
                                "duration": total_duration,
                                "total_clips": num_clips,
                                "clip_duration": clip_duration
                            },
                            "clip": {
                                "index": i,
                                "total": num_clips,
                                "duration": duration,
                                "start_time": start_time,
                                "end_time": end_time,
                                "timestamp": f"{int(start_time//60):02d}:{int(start_time%60):02d} - {int(end_time//60):02d}:{int(end_time%60):02d}"
                            }
                        }
                    }
                    video_paths.append(Data(data=clip_data))
                    
                except Exception as e:
                    self.log(f"Error processing clip {i}: {str(e)}", "ERROR")
                    raise
            
            self.log(f"Created {len(video_paths)} clips in {output_dir}")
            return video_paths
            
        except Exception as e:
            self.log(f"Error processing video: {str(e)}", "ERROR")
            raise

    def process(self) -> List[Data]:
        """Process the input video and return a list of Data objects containing the clips."""
        try:
            # Get the input video path from the previous component
            if not hasattr(self, 'videodata') or not isinstance(self.videodata, list) or len(self.videodata) != 1:
                raise ValueError("Please provide exactly one video")
            
            video_path = self.videodata[0].data.get('text')
            if not video_path or not os.path.exists(video_path):
                raise ValueError("Invalid video path")
            
            # Process the video
            return self.process_video(video_path, self.clip_duration, self.include_original)
            
        except Exception as e:
            self.log(f"Error in split video component: {str(e)}", "ERROR")
            raise
