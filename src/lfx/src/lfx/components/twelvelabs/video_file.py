from pathlib import Path

from lfx.base.data import BaseFileComponent
from lfx.io import FileInput
from lfx.schema import Data, DataFrame
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component

disable_component_in_astra_cloud_msg = (
    "Video processing is not supported in Astra cloud environment. "
    "Video components require local file system access for processing. "
    "Please use local storage mode or process videos locally before uploading."
)


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
        *BaseFileComponent.get_base_outputs(),
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Process video files."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(disable_component_in_astra_cloud_msg)
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

    def load_files(self) -> DataFrame:
        """Load video files and return a list of Data objects."""
        # Check if we're in Astra cloud environment and raise an error if we are.
        raise_error_if_astra_cloud_disable_component(disable_component_in_astra_cloud_msg)

        try:
            self.log("DEBUG: Starting video file load")
            if not hasattr(self, "file_path") or not self.file_path:
                self.log("DEBUG: No video file path provided")
                return DataFrame()

            # Use the base class helper to resolve paths
            resolved_paths = self._resolve_paths_from_value(self.file_path)

            video_data_list = []
            for _, path_str in resolved_paths:
                # Resolve to absolute path
                resolved_path = Path(self.resolve_path(path_str))

                if not resolved_path.exists():
                    msg = f"Video file not found at path: {resolved_path}"
                    self.log(f"WARNING: {msg}")
                    if not getattr(self, "silent_errors", False):
                        raise FileNotFoundError(msg)
                    continue

                file_size = resolved_path.stat().st_size
                video_data_list.append(
                    {
                        "text": str(resolved_path),
                        "metadata": {"source": str(resolved_path), "type": "video", "size": file_size},
                    }
                )

            if not video_data_list:
                return DataFrame()

            result = DataFrame(data=video_data_list)
            self.log(f"DEBUG: Returning {len(video_data_list)} video Data objects")
        except (FileNotFoundError, PermissionError, OSError) as e:
            self.log(f"DEBUG: File error in video load_files: {e!s}", "ERROR")
            if not getattr(self, "silent_errors", False):
                raise
            return DataFrame()
        except ImportError as e:
            self.log(f"DEBUG: Import error in video load_files: {e!s}", "ERROR")
            if not getattr(self, "silent_errors", False):
                raise
            return DataFrame()
        except (ValueError, TypeError) as e:
            self.log(f"DEBUG: Value or type error in video load_files: {e!s}", "ERROR")
            if not getattr(self, "silent_errors", False):
                raise
            return DataFrame()
        else:
            return result
