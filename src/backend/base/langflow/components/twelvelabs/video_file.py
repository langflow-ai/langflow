from langflow.base.data import BaseFileComponent
from langflow.io import FileInput
from langflow.schema import Data
import os


class VideoFileComponent(BaseFileComponent):
    """Handles loading and processing of individual or zipped text files.

    This component supports processing multiple valid files within a zip archive,
    resolving paths, validating file types, and optionally using multithreading for processing.
    """

    display_name = "Video File"
    description = "Load a video file to be used in your project."
    icon = "video"
    name = "VideoFile"

    VALID_EXTENSIONS = ["mp4"]

    inputs = [
        FileInput(
            display_name="Video File",
            name="file_path",
            file_types=["mp4"],
            required=True,
            info="Upload a video file (MP4 format)",
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
                
                # Create video data structure
                file.data = Data(data={"path": file_path})
                processed_files.append(file)
                self.log(f"DEBUG: Processed video file: {file_path}")
                
            except Exception as e:
                self.log(f"Error processing video file: {str(e)}", "ERROR")
                if not self.silent_errors:
                    raise
        
        return processed_files

    def load_files(self) -> Data:
        """Load video files and return in proper format"""
        try:
            self.log("DEBUG: Starting video file load")
            if not hasattr(self, 'file_path') or not self.file_path:
                self.log("DEBUG: No video file path provided")
                return Data(data={"error": "No video file path provided"})

            self.log(f"DEBUG: Loading video from path: {self.file_path}")
            
            # Create BaseFile with path
            base_file = self.BaseFile(
                path=self.file_path,
                data=None
            )
            
            processed_files = self.process_files([base_file])
            
            if processed_files:
                # Create the data structure that TwelveLabsEmbed2 expects
                # Return a single Data object with the path
                result = {
                    "data": {
                        "path": str(processed_files[0].path)
                    }
                }
                self.log(f"DEBUG: Final output structure: {result}")
                return Data(**result)
            
            return Data(data={"error": "Failed to process video file"})
            
        except Exception as e:
            self.log(f"DEBUG: Error in video load_files: {str(e)}", "ERROR")
            return Data(data={"error": str(e)})
