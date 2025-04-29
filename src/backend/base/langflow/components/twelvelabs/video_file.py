from langflow.base.data import BaseFileComponent
from langflow.io import FileInput
from langflow.schema import Data
import os


class VideoFileComponent(BaseFileComponent):
    """Handles loading and processing of video files.

    This component supports processing video files in common video formats.
    """

    display_name = "Video File"
    description = "Load a video file in common video formats."
    icon = "TwelveLabs"
    name = "VideoFile"

    VALID_EXTENSIONS = [
        # Common video formats
        "mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", 
        "mpg", "mpeg", "m4v", "3gp", "3g2", "m2v",
        # Professional video formats
        "mxf", "dv", "vob",
        # Additional video formats
        "ogv", "rm", "rmvb", "amv", "divx", "m2ts", "mts", "ts",
        "qt", "yuv", "y4m"
    ]

    inputs = [
        FileInput(
            display_name="Video File",
            name="file_path",
            file_types=[
                # Common video formats
                "mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", 
                "mpg", "mpeg", "m4v", "3gp", "3g2", "m2v",
                # Professional video formats
                "mxf", "dv", "vob",
                # Additional video formats
                "ogv", "rm", "rmvb", "amv", "divx", "m2ts", "mts", "ts",
                "qt", "yuv", "y4m"
            ],
            required=True,
            info="Upload a video file in any common video format supported by ffmpeg",
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Process video files"""
        self.log(f"DEBUG: Processing video files: {len(file_list)}")
        
        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        processed_files = []
        for file in file_list:
            try:
                file_path = str(file.path)
                self.log(f"DEBUG: Processing video file: {file_path}")
                
                # Verify file exists
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Video file not found: {file_path}")
                
                # Verify extension
                if not file_path.lower().endswith(tuple(self.VALID_EXTENSIONS)):
                    raise ValueError(f"Invalid file type. Expected: {', '.join(self.VALID_EXTENSIONS)}")
                
                # Create a dictionary instead of a Document
                doc_data = {
                    "text": file_path,
                    "metadata": {
                        "source": file_path,
                        "type": "video"
                    }
                }
                
                # Pass the dictionary to Data
                file.data = Data(data=doc_data)
                
                self.log(f"DEBUG: Created data: {doc_data}")
                processed_files.append(file)
                
            except Exception as e:
                self.log(f"Error processing video file: {str(e)}", "ERROR")
                raise
        
        return processed_files

    def load_files(self) -> list[Data]:
        """Load video files and return a list of Data objects"""
        try:
            self.log("DEBUG: Starting video file load")
            if not hasattr(self, 'file_path') or not self.file_path:
                self.log("DEBUG: No video file path provided")
                return []

            self.log(f"DEBUG: Loading video from path: {self.file_path}")
            
            # Verify file exists
            if not os.path.exists(self.file_path):
                self.log(f"DEBUG: Video file not found at path: {self.file_path}")
                return []
            
            # Verify file size
            file_size = os.path.getsize(self.file_path)
            self.log(f"DEBUG: Video file size: {file_size} bytes")
            
            # Create a proper Data object with the video path
            video_data = {
                "text": self.file_path,
                "metadata": {
                    "source": self.file_path,
                    "type": "video",
                    "size": file_size
                }
            }
            
            self.log(f"DEBUG: Created video data: {video_data}")
            result = [Data(data=video_data)]
            
            # Log the result to verify it's a proper Data object
            self.log(f"DEBUG: Returning list with Data objects")
            return result
            
        except Exception as e:
            self.log(f"DEBUG: Error in video load_files: {str(e)}", "ERROR")
            import traceback
            self.log(f"DEBUG: Traceback: {traceback.format_exc()}", "ERROR")
            return []  # Return empty list on error
