from pathlib import Path

from langflow.base.data import BaseFileComponent
from langflow.io import FileInput
from langflow.schema import Data


class VideoFileComponent(BaseFileComponent):
    """Handles loading and processing of video files.

    This component supports processing video files in common video formats.
    """

    display_name = "Video File"
    description = "Load a video file in common video formats."
    icon = "TwelveLabs"
    name = "VideoFile"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    VALID_EXTENSIONS = [
        # Common video formats
        "mp4",
        "avi",
        "mov",
        "mkv",
        "webm",
        "flv",
        "wmv",
        "mpg",
        "mpeg",
        "m4v",
        "3gp",
        "3g2",
        "m2v",
        # Professional video formats
        "mxf",
        "dv",
        "vob",
        # Additional video formats
        "ogv",
        "rm",
        "rmvb",
        "amv",
        "divx",
        "m2ts",
        "mts",
        "ts",
        "qt",
        "yuv",
        "y4m",
    ]

    inputs = [
        FileInput(
            display_name="Video File",
            name="file_path",
            file_types=[
                # Common video formats
                "mp4",
                "avi",
                "mov",
                "mkv",
                "webm",
                "flv",
                "wmv",
                "mpg",
                "mpeg",
                "m4v",
                "3gp",
                "3g2",
                "m2v",
                # Professional video formats
                "mxf",
                "dv",
                "vob",
                # Additional video formats
                "ogv",
                "rm",
                "rmvb",
                "amv",
                "divx",
                "m2ts",
                "mts",
                "ts",
                "qt",
                "yuv",
                "y4m",
            ],
            required=True,
            info="Upload a video file in any common video format supported by ffmpeg",
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Process video files."""
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
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    error_msg = f"Video file not found: {file_path}"
                    raise FileNotFoundError(error_msg)

                # Verify extension
                if not file_path.lower().endswith(tuple(self.VALID_EXTENSIONS)):
                    error_msg = f"Invalid file type. Expected: {', '.join(self.VALID_EXTENSIONS)}"
                    raise ValueError(error_msg)

                # Create a dictionary instead of a Document
                doc_data = {"text": file_path, "metadata": {"source": file_path, "type": "video"}}

                # Pass the dictionary to Data
                file.data = Data(data=doc_data)

                self.log(f"DEBUG: Created data: {doc_data}")
                processed_files.append(file)

            except Exception as e:
                self.log(f"Error processing video file: {e!s}", "ERROR")
                raise

        return processed_files

    def load_files(self) -> list[Data]:
        """Load video files and return a list of Data objects."""
        try:
            self.log("DEBUG: Starting video file load")
            if not hasattr(self, "file_path") or not self.file_path:
                self.log("DEBUG: No video file path provided")
                return []

            self.log(f"DEBUG: Loading video from path: {self.file_path}")

            # Verify file exists
            file_path_obj = Path(self.file_path)
            if not file_path_obj.exists():
                self.log(f"DEBUG: Video file not found at path: {self.file_path}")
                return []

            # Verify file size
            file_size = file_path_obj.stat().st_size
            self.log(f"DEBUG: Video file size: {file_size} bytes")

            # Create a proper Data object with the video path
            video_data = {
                "text": self.file_path,
                "metadata": {"source": self.file_path, "type": "video", "size": file_size},
            }

            self.log(f"DEBUG: Created video data: {video_data}")
            result = [Data(data=video_data)]

            # Log the result to verify it's a proper Data object
            self.log("DEBUG: Returning list with Data objects")
        except (FileNotFoundError, PermissionError, OSError) as e:
            self.log(f"DEBUG: File error in video load_files: {e!s}", "ERROR")
            return []
        except ImportError as e:
            self.log(f"DEBUG: Import error in video load_files: {e!s}", "ERROR")
            return []
        except (ValueError, TypeError) as e:
            self.log(f"DEBUG: Value or type error in video load_files: {e!s}", "ERROR")
            return []
        else:
            return result
