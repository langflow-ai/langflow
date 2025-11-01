"""Multi-modal Input Component for Langflow

REQUIRED CUSTOM PACKAGES:
- yt-dlp>=2023.1.0       # OPTIONAL: For YouTube audio/video download support
- ffmpeg                 # SYSTEM REQUIREMENT: For video frame extraction (not a Python package)

INSTALLATION COMMANDS:
uv pip install yt-dlp  # Optional, for YouTube support

SYSTEM REQUIREMENTS:
- FFmpeg must be installed and available in PATH for video processing
  Windows: winget install FFmpeg
  Mac: brew install ffmpeg
  Linux: sudo apt install ffmpeg

SUPPORTED MEDIA SOURCES:
- Local file uploads (audio, video, image)
- Direct URLs (any direct link to media files)
- YouTube URLs (requires yt-dlp)
- Google Drive public links
"""

import base64
import os
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

import requests
from openai import OpenAI

from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from langflow.custom import Component
from langflow.inputs.inputs import BoolInput
from langflow.io import (
    DropdownInput,
    FileInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    TabInput,
)
from langflow.schema.message import Message
from langflow.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)


class MultiModalInputComponent(Component):
    display_name = "Multi-modal Input"
    description = "Receives audio, video, or image input and transforms it into text using AI analysis."
    icon = "repeat"
    name = "Multi-modal Input"
    beta = True

    inputs = [
        TabInput(
            name="input_type",
            display_name="Input Type",
            options=["Audio", "Video", "Image"],
            info="Type of input to process. Audio, Video and Image will be transcribed/analyzed automatically.",
            real_time_refresh=True,
            value="Audio",
        ),
        DropdownInput(
            name="model_provider",
            display_name="Model Provider",
            options=["OpenAI"],
            value="OpenAI",
            info="Select the AI model provider for processing",
            real_time_refresh=True,
            show=False,
            options_metadata=[{"icon": "OpenAI"}],
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="Your OpenAI API key for audio/video/image processing.",
            required=True,
            show=False,
        ),
        FileInput(
            name="media_file",
            display_name="Media File",
            file_types=[
                "mp3",
                "mp4",
                "mpeg",
                "mpga",
                "wav",
                "webm",
                "avi",
                "mov",
                "mkv",
                "flv",
                "wmv",
                "jpg",
                "jpeg",
                "png",
                "gif",
                "webp",
            ],
            info="Upload audio/video/image file for processing (for Audio/Video/Image types).",
            show=False,
        ),
        MessageTextInput(
            name="media_url",
            display_name="Media URL",
            info="URL link to audio/video/image file. Supports direct URLs, YouTube, Google Drive, etc. Used if no file is uploaded.",
            show=False,
        ),
        BoolInput(
            name="should_store_message",
            display_name="Store Messages",
            info="Store the message in the history.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
            value=MESSAGE_SENDER_USER,
            info="Type of sender.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            value=MESSAGE_SENDER_NAME_USER,
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        FileInput(
            name="files",
            display_name="Files",
            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,
            info="Files to be sent with the message.",
            advanced=True,
            is_list=True,
        ),
        MessageTextInput(
            name="background_color",
            display_name="Background Color",
            info="The background color of the icon.",
            advanced=True,
        ),
        MessageTextInput(
            name="chat_icon",
            display_name="Icon",
            info="The icon of the message.",
            advanced=True,
        ),
        MessageTextInput(
            name="text_color",
            display_name="Text Color",
            info="The text color of the name",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="message_response"),
    ]

    def download_media_from_url(self, url: str, media_type: str) -> str:
        """Download media file from URL and return local path."""
        try:
            # Parse URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                raise ValueError("Invalid URL: missing scheme (http/https)")

            self.log(f"Downloading {media_type} from URL: {url}")

            # Handle different URL types
            if "youtube.com" in url or "youtu.be" in url:
                self.log("Detected YouTube URL, attempting to use yt-dlp downloader")
                try:
                    return self.download_youtube_media(url, media_type)
                except ImportError:
                    self.log("yt-dlp not available, falling back to direct download (may not work for YouTube)")
                    # For YouTube URLs, direct download usually doesn't work, but we can try
                    return self.download_direct_url(url, media_type)
                except Exception as e:
                    self.log(f"YouTube download failed: {e}")
                    # Try direct download as fallback
                    self.log("Attempting direct download as fallback...")
                    return self.download_direct_url(url, media_type)
            elif "drive.google.com" in url:
                self.log("Detected Google Drive URL, using direct downloader")
                return self.download_google_drive_media(url)
            else:
                self.log("Detected direct URL, using requests downloader")
                return self.download_direct_url(url, media_type)

        except Exception as e:
            error_msg = f"Failed to download media from URL: {e!s}"
            self.log(f"Download error: {error_msg}")
            raise RuntimeError(error_msg)

    def download_direct_url(self, url: str, media_type: str) -> str:
        """Download media from direct URL."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            # Determine file extension
            content_type = response.headers.get("content-type", "").lower()
            if media_type == "Audio":
                ext = ".mp3" if "audio" in content_type else ".mp3"
            elif media_type == "Video":
                ext = ".mp4" if "video" in content_type else ".mp4"
            elif media_type == "Image":
                if "jpeg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                elif "gif" in content_type:
                    ext = ".gif"
                else:
                    ext = ".jpg"
            else:
                ext = ".tmp"

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

            # Download file
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

            temp_file.close()
            return temp_file.name

        except Exception as e:
            raise RuntimeError(f"Failed to download from direct URL: {e!s}")

    def download_youtube_media(self, url: str, media_type: str) -> str:
        """Download media from YouTube URL using yt-dlp if available."""
        try:
            import yt_dlp

            temp_dir = tempfile.mkdtemp()
            self.log(f"Created temporary directory: {temp_dir}")

            if media_type == "Audio":
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                    "ignoreerrors": True,
                    "no_warnings": False,  # Enable warnings for debugging
                    "verbose": True,  # Enable verbose output for debugging
                }
            else:  # Video
                # Use more flexible format selection for videos
                ydl_opts = {
                    "format": "best[height<=1080]/best[ext=mp4]/best",  # More flexible format selection
                    "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                    "ignoreerrors": True,
                    "no_warnings": False,  # Enable warnings for debugging
                    "verbose": True,  # Enable verbose output for debugging
                }

            self.log(f"YouTube download options: {ydl_opts}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First, try to get available formats to debug
                try:
                    self.log("Extracting video information...")
                    info = ydl.extract_info(url, download=False)
                    available_formats = info.get("formats", [])
                    if not available_formats:
                        raise RuntimeError("No formats available for this video")

                    # Log available formats for debugging
                    self.log(f"Available formats: {len(available_formats)} formats found")
                    for i, fmt in enumerate(available_formats[:5]):  # Show first 5 formats
                        self.log(
                            f"Format {i}: {fmt.get('format_id', 'N/A')} - {fmt.get('ext', 'N/A')} - {fmt.get('height', 'N/A')}p"
                        )

                    # Check if video is available
                    if info.get("availability") == "private":
                        raise RuntimeError("This video is private and cannot be downloaded")
                    if info.get("availability") == "unavailable":
                        raise RuntimeError("This video is unavailable in your region")

                except Exception as format_error:
                    self.log(f"Warning: Could not extract format info: {format_error}")

                # Proceed with download
                self.log("Starting download...")
                ydl.download([url])

            # Find downloaded file
            files = os.listdir(temp_dir)
            self.log(f"Files in temp directory: {files}")

            if not files:
                # Check if there are any hidden files or subdirectories
                all_files = []
                for root, dirs, filenames in os.walk(temp_dir):
                    for filename in filenames:
                        all_files.append(os.path.join(root, filename))

                self.log(f"All files found (including subdirectories): {all_files}")

                if not all_files:
                    raise RuntimeError(
                        "No file downloaded. This could be due to: 1) Video restrictions, 2) Network issues, 3) yt-dlp version incompatibility"
                    )

                # Use the first file found
                return all_files[0]

            # Return the first file found
            downloaded_file = os.path.join(temp_dir, files[0])
            self.log(f"Successfully downloaded: {downloaded_file}")
            return downloaded_file

        except ImportError:
            raise RuntimeError("yt-dlp not installed. Install with: pip install yt-dlp")
        except Exception as e:
            # Clean up temp directory on error
            try:
                if "temp_dir" in locals():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass

            # Provide more helpful error message
            error_msg = str(e)
            if "Requested format is not available" in error_msg:
                raise RuntimeError(
                    f"YouTube format error: {error_msg}. Try using a different video or check if the video is available."
                )
            if "Video unavailable" in error_msg:
                raise RuntimeError(
                    f"YouTube video unavailable: {error_msg}. The video may be private, deleted, or region-restricted."
                )
            if "Sign in" in error_msg:
                raise RuntimeError(
                    f"YouTube requires authentication: {error_msg}. This video may be age-restricted or require login."
                )
            raise RuntimeError(f"Failed to download from YouTube: {error_msg}")

    def download_google_drive_media(self, url: str) -> str:
        """Download media from Google Drive URL."""
        try:
            # Extract file ID from Google Drive URL
            if "/d/" in url:
                file_id = url.split("/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                raise ValueError("Could not extract file ID from Google Drive URL")

            # Create download URL
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

            # Download file
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

            temp_file.close()
            return temp_file.name

        except Exception as e:
            raise RuntimeError(f"Failed to download from Google Drive: {e!s}")

    def update_build_config(self, build_config, field_value, field_name=None):
        if field_name == "input_type":
            # Extract input type from the selected value
            input_type = field_value if isinstance(field_value, str) else "Audio"

            # Define field visibility map
            field_map = {
                "Audio": ["media_file", "media_url", "model_provider", "api_key"],
                "Video": ["media_file", "media_url", "model_provider", "api_key"],
                "Image": ["media_file", "media_url", "model_provider", "api_key"],
            }

            # Hide all dynamic fields first
            for field_name in ["media_file", "media_url", "model_provider", "api_key"]:
                if field_name in build_config:
                    build_config[field_name]["show"] = False

            # Show fields based on selected input type
            if input_type in field_map:
                for field_name in field_map[input_type]:
                    if field_name in build_config:
                        build_config[field_name]["show"] = True

        elif field_name == "model_provider":
            # Update API key label based on provider
            if field_value == "OpenAI":
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["info"] = "Your OpenAI API key for audio/video/image processing."
            # Future providers can be added here
            # elif field_value == "Anthropic":
            #     build_config["api_key"]["display_name"] = "Anthropic API Key"
            #     build_config["api_key"]["info"] = "Your Anthropic API key for processing."

        return build_config

    def process_audio(self, audio_file_path: str, api_key: str) -> str:
        """Process audio file using OpenAI Whisper API."""
        try:
            if not os.path.exists(audio_file_path):
                return f"Error: Audio file not found at {audio_file_path}"

            file_size = os.path.getsize(audio_file_path)
            if file_size == 0:
                return "Error: Audio file is empty"

            client = OpenAI(api_key=api_key)
            with open(audio_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

            return transcript.text

        except Exception as e:
            return f"Error processing audio: {e!s}"

    def check_ffmpeg_availability(self) -> bool:
        """Check if ffmpeg is available in the system."""
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def extract_frames(self, video_path: str, num_frames: int = 3) -> tuple[list[str], str]:
        """Extract frames from video and return frame paths and temp directory."""
        tmp_dir = tempfile.mkdtemp()
        self.log(f"Created temporary directory for frame extraction: {tmp_dir}")

        # First, let's check if the video file is valid
        try:
            # Check video file info
            probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            self.log("Video file info retrieved successfully")
        except subprocess.CalledProcessError as e:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            raise RuntimeError(f"Invalid or corrupted video file. FFprobe error: {e.stderr}")

        # Try multiple frame extraction strategies
        strategies = [
            # Strategy 1: Standard frame extraction
            {
                "name": "Standard extraction",
                "cmd": [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vf",
                    f"fps=1/{max(1, num_frames)}",
                    "-vframes",
                    str(num_frames),
                    os.path.join(tmp_dir, "frame_%03d.jpg"),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                ],
            },
            # Strategy 2: Extract frames at specific timestamps
            {
                "name": "Timestamp-based extraction",
                "cmd": [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vf",
                    "select='eq(pict_type,I)'",
                    "-vsync",
                    "vfr",
                    "-vframes",
                    str(num_frames),
                    os.path.join(tmp_dir, "frame_%03d.jpg"),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                ],
            },
            # Strategy 3: Extract frames at regular intervals
            {
                "name": "Interval-based extraction",
                "cmd": [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vf",
                    "select='not(mod(n,30))'",
                    "-vframes",
                    str(num_frames),
                    os.path.join(tmp_dir, "frame_%03d.jpg"),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                ],
            },
            # Strategy 4: Simple frame extraction without filters
            {
                "name": "Simple extraction",
                "cmd": [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vframes",
                    str(num_frames),
                    os.path.join(tmp_dir, "frame_%03d.jpg"),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                ],
            },
        ]

        for i, strategy in enumerate(strategies):
            try:
                self.log(f"Trying frame extraction strategy {i + 1}: {strategy['name']}")
                subprocess.run(strategy["cmd"], check=True, capture_output=True, text=True)

                # Check if frames were extracted
                frame_files = [os.path.join(tmp_dir, f) for f in sorted(os.listdir(tmp_dir)) if f.endswith(".jpg")]

                if frame_files:
                    self.log(f"Successfully extracted {len(frame_files)} frames using strategy: {strategy['name']}")
                    return frame_files, tmp_dir
                self.log(f"Strategy {strategy['name']} completed but no frames found")

            except subprocess.CalledProcessError as e:
                self.log(f"Strategy {strategy['name']} failed: {e.stderr}")
                continue

        # If all strategies failed, try to get at least one frame
        try:
            self.log("All strategies failed, trying to extract just one frame...")
            simple_cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vframes",
                "1",
                os.path.join(tmp_dir, "single_frame.jpg"),
                "-hide_banner",
                "-loglevel",
                "error",
            ]
            subprocess.run(simple_cmd, check=True, capture_output=True, text=True)

            single_frame = os.path.join(tmp_dir, "single_frame.jpg")
            if os.path.exists(single_frame):
                self.log("Successfully extracted one frame as fallback")
                return [single_frame], tmp_dir

        except subprocess.CalledProcessError as e:
            self.log(f"Even single frame extraction failed: {e.stderr}")

        # Clean up and raise error
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        raise RuntimeError(
            "Failed to extract any frames from video. The video file may be corrupted, in an unsupported format, or too short."
        )

    def query_gpt4v(self, image_paths: list[str], api_key: str) -> str:
        """Analyze video frames using GPT-4V."""
        client = OpenAI(api_key=api_key)
        image_data = []
        for path in image_paths:
            with open(path, "rb") as img_file:
                b64_img = base64.b64encode(img_file.read()).decode("utf-8")
                image_data.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}})

        prompt = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze these frames from a video and provide a comprehensive description of the content, including: the main subjects/objects, setting/environment, actions or events taking place, visual style, and any notable details. Create a coherent narrative that connects the frames as part of a single video sequence.",
                        },
                        *image_data,
                    ],
                }
            ],
            "max_tokens": 800,
        }
        response = client.chat.completions.create(**prompt)
        return response.choices[0].message.content.strip()

    def process_video(self, video_file_path: str, api_key: str) -> str:
        """Process video file using GPT-4V."""
        try:
            if not self.check_ffmpeg_availability():
                return """Error: FFmpeg is required but not found on your system.
                
Please install FFmpeg:

Windows:
1. Download from https://ffmpeg.org/download.html
2. Add to PATH environment variable
OR use: winget install FFmpeg

Mac:
brew install ffmpeg

Linux:
sudo apt update && sudo apt install ffmpeg
OR
sudo yum install ffmpeg

After installation, restart your application."""

            if not os.path.exists(video_file_path):
                return f"Error: Video file not found at {video_file_path}"

            # Check file size
            file_size = os.path.getsize(video_file_path)
            if file_size == 0:
                return "Error: Video file is empty"

            self.log(f"Processing video file: {video_file_path} (size: {file_size} bytes)")

            # Try to extract frames and analyze with GPT-4V
            try:
                frames, frames_dir = self.extract_frames(video_file_path, num_frames=3)

                if not frames:
                    return "Error: Could not extract frames from video"

                self.log(f"Successfully extracted {len(frames)} frames for analysis")
                summary = self.query_gpt4v(frames, api_key)

                # Cleanup temporary files
                cleanup_paths = [frames_dir] + frames
                for p in cleanup_paths:
                    try:
                        if os.path.isfile(p):
                            os.remove(p)
                        elif os.path.isdir(p):
                            shutil.rmtree(p)
                    except (OSError, FileNotFoundError):
                        pass

                return summary

            except Exception as frame_error:
                self.log(f"Frame extraction failed: {frame_error}")

                # Fallback: Try to get video metadata and provide basic analysis
                try:
                    self.log("Attempting fallback analysis using video metadata...")

                    # Get video information using ffprobe
                    probe_cmd = [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_format",
                        "-show_streams",
                        video_file_path,
                    ]

                    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                    video_info = result.stdout

                    # Extract basic video information
                    import json

                    try:
                        info = json.loads(video_info)
                        format_info = info.get("format", {})
                        streams = info.get("streams", [])

                        # Find video stream
                        video_stream = None
                        for stream in streams:
                            if stream.get("codec_type") == "video":
                                video_stream = stream
                                break

                        # Build basic video description
                        description_parts = []

                        if format_info:
                            duration = format_info.get("duration")
                            if duration:
                                duration_sec = float(duration)
                                minutes = int(duration_sec // 60)
                                seconds = int(duration_sec % 60)
                                description_parts.append(f"Duration: {minutes}m {seconds}s")

                            size = format_info.get("size")
                            if size:
                                size_mb = int(size) / (1024 * 1024)
                                description_parts.append(f"File size: {size_mb:.1f} MB")

                        if video_stream:
                            width = video_stream.get("width")
                            height = video_stream.get("height")
                            if width and height:
                                description_parts.append(f"Resolution: {width}x{height}")

                            codec = video_stream.get("codec_name")
                            if codec:
                                description_parts.append(f"Codec: {codec}")

                        if description_parts:
                            basic_info = " | ".join(description_parts)
                            return f"Video Analysis (Metadata Only):\n\n{basic_info}\n\nNote: Frame extraction failed, so detailed visual analysis is not available. The video file may be corrupted, in an unsupported format, or too short for frame extraction."
                        return "Video Analysis: Unable to extract detailed information. The video file may be corrupted or in an unsupported format."

                    except json.JSONDecodeError:
                        return "Video Analysis: Unable to parse video metadata. The video file may be corrupted."

                except subprocess.CalledProcessError as probe_error:
                    return f"Video Analysis: Unable to analyze video file. Error: {probe_error.stderr}"

        except Exception as e:
            return f"Error processing video: {e!s}"

    def process_image(self, image_file_path: str, api_key: str) -> str:
        """Process image file using OpenAI GPT-4V API."""
        try:
            if not os.path.exists(image_file_path):
                return f"Error: Image file not found at {image_file_path}"

            file_size = os.path.getsize(image_file_path)
            if file_size == 0:
                return "Error: Image file is empty"

            # Read and encode image
            with open(image_file_path, "rb") as f:
                image_data = f.read()

            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Get API key
            if hasattr(api_key, "get_secret_value"):
                api_key = api_key.get_secret_value()

            client = OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe the image or extract text if present."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ],
                    }
                ],
                max_tokens=1024,
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error processing image: {e!s}"

    async def message_response(self) -> Message:
        background_color = self.background_color
        text_color = self.text_color
        icon = self.chat_icon

        # Process input based on type
        processed_text = ""

        # Extract input type from TabInput
        input_type = self.input_type if isinstance(self.input_type, str) else "Audio"

        if input_type == "Audio":
            if not self.media_file and not self.media_url:
                processed_text = "Error: No audio file or URL provided"
            elif not self.api_key:
                processed_text = "Error: API key required for audio processing"
            # Use URL if no file provided
            elif not self.media_file and self.media_url:
                try:
                    downloaded_file = self.download_media_from_url(self.media_url, "Audio")
                    processed_text = self.process_audio(downloaded_file, self.api_key)
                    # Cleanup downloaded file
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                except Exception as e:
                    processed_text = f"Error downloading audio from URL: {e!s}"
            else:
                processed_text = self.process_audio(self.media_file, self.api_key)
        elif input_type == "Video":
            if not self.media_file and not self.media_url:
                processed_text = "Error: No video file or URL provided"
            elif not self.api_key:
                processed_text = "Error: API key required for video processing"
            # Use URL if no file provided
            elif not self.media_file and self.media_url:
                try:
                    downloaded_file = self.download_media_from_url(self.media_url, "Video")
                    processed_text = self.process_video(downloaded_file, self.api_key)
                    # Cleanup downloaded file
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                except Exception as e:
                    processed_text = f"Error downloading video from URL: {e!s}"
            else:
                processed_text = self.process_video(self.media_file, self.api_key)
        elif input_type == "Image":
            if not self.media_file and not self.media_url:
                processed_text = "Error: No image file or URL provided"
            elif not self.api_key:
                processed_text = "Error: API key required for image processing"
            # Use URL if no file provided
            elif not self.media_file and self.media_url:
                try:
                    downloaded_file = self.download_media_from_url(self.media_url, "Image")
                    processed_text = self.process_image(downloaded_file, self.api_key)
                    # Cleanup downloaded file
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                except Exception as e:
                    processed_text = f"Error downloading image from URL: {e!s}"
            else:
                processed_text = self.process_image(self.media_file, self.api_key)
        else:
            processed_text = "Error: Invalid input type"

        message = await Message.create(
            text=processed_text,
            sender=self.sender,
            sender_name=self.sender_name,
            session_id=self.session_id,
            files=self.files,
            properties={
                "background_color": background_color,
                "text_color": text_color,
                "icon": icon,
            },
        )
        if self.session_id and isinstance(message, Message) and self.should_store_message:
            stored_message = await self.send_message(
                message,
            )
            self.message.value = stored_message
            message = stored_message

        self.status = message
        return message
