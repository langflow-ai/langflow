import base64
import time
from typing import Any

import requests

# Import Google GenAI for Veo video generation
from google import genai
from google.genai import types
from lfx.custom import Component
from lfx.io import DropdownInput, HandleInput, IntInput, Output, SecretStrInput, TabInput
from lfx.schema import Data, Message
from openai import OpenAI


class ModalConverterComponent(Component):
    display_name = "Modal Converter"
    description = "Convert text to audio, image, or video using AI models."
    icon = "repeat"
    beta = True

    inputs = [
        HandleInput(
            name="input_text",
            display_name="Input",
            input_types=["Message", "Data", "DataFrame"],
            info="Text input to convert to audio, image, or video",
            required=True,
        ),
        TabInput(
            name="output_type",
            display_name="Output Type",
            options=["Audio", "Image", "Video"],
            info="Select the desired output media type",
            real_time_refresh=True,
            value="Audio",
        ),
        # Model provider for Audio and Image
        DropdownInput(
            name="audio_image_provider",
            display_name="Model Provider",
            options=["OpenAI"],
            value="OpenAI",
            real_time_refresh=True,
            show=False,
            options_metadata=[{"icon": "OpenAI"}],
        ),
        # Model provider for Video
        DropdownInput(
            name="video_provider",
            display_name="Model Provider",
            options=["Google Generative AI"],
            value="Google Generative AI",
            real_time_refresh=True,
            show=False,
            options_metadata=[{"icon": "GoogleGenerativeAI"}],
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="Your OpenAI API key for generating audio, images, and videos",
            required=True,
            show=False,
        ),
        SecretStrInput(
            name="gemini_api_key",
            display_name="Gemini API Key",
            info="Your Google Gemini API key for generating videos with Veo",
            required=True,
            show=False,
        ),
        # Audio-specific options
        DropdownInput(
            name="voice",
            display_name="Voice",
            info="Select the voice for audio generation",
            options=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            value="alloy",
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="audio_format",
            display_name="Audio Format",
            info="Select audio format",
            options=["mp3", "opus", "aac", "flac", "wav", "pcm"],
            value="mp3",
            advanced=True,
            show=False,
        ),
        IntInput(
            name="speed",
            display_name="Speed",
            info="Speed of the generated audio. Values range from 0.25 to 4.0.",
            value=1,
            advanced=True,
            show=False,
        ),
        # Image-specific options
        DropdownInput(
            name="image_model",
            display_name="Image Model",
            options=["dall-e-2", "dall-e-3"],
            value="dall-e-3",
            info="The DALL·E model version to use",
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="image_size",
            display_name="Image Size",
            value="1024x1024",
            info="Size of the generated image",
            options=["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"],
            advanced=True,
            show=False,
        ),
        IntInput(
            name="num_images",
            display_name="Number of Images",
            value=1,
            info="Number of images to generate",
            advanced=True,
            show=False,
        ),
        # Video-specific options for Google Veo
        DropdownInput(
            name="video_model",
            display_name="Model",
            options=[
                "veo-3.0-generate-preview",  # Latest Veo 3.0 model
                "veo-2.0-generate-001",  # Veo 2.0 model (requires GCP billing)
                "models/veo-2.0-generate-001",  # Full format for Veo 2.0
            ],
            value="veo-3.0-generate-preview",
            info="Veo model to use for video generation",
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            options=[
                "16:9",  # Widescreen
                "9:16",  # Portrait/Vertical
            ],
            value="16:9",
            info="Video format ratio",
            advanced=True,
            show=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Audio Data",
            name="audio_output",
            method="generate_audio",
        )
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "output_type":
            # Start with empty outputs
            frontend_node["outputs"] = []

            # Add only the selected output type
            if field_value == "Audio":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Audio Data",
                        name="audio_output",
                        method="generate_audio",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Audio Base64",
                        name="audio_base64",
                        method="generate_audio_base64",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Markdown",
                        name="markdown_output",
                        method="generate_markdown",
                    ).to_dict()
                )
            elif field_value == "Image":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Image Data",
                        name="image_output",
                        method="generate_image",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Image URL",
                        name="image_url",
                        method="generate_image_url",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Markdown",
                        name="markdown_output",
                        method="generate_markdown",
                    ).to_dict()
                )
            elif field_value == "Video":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Video Data",
                        name="video_output",
                        method="generate_video",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Video URLs",
                        name="video_urls",
                        method="generate_video_urls",
                    ).to_dict()
                )
                frontend_node["outputs"].append(
                    Output(
                        display_name="Markdown",
                        name="markdown_output",
                        method="generate_markdown",
                    ).to_dict()
                )

        return frontend_node

    def update_build_config(self, build_config, field_value, field_name=None):
        if field_name == "output_type":
            # Extract output type from the selected value
            output_type = field_value if isinstance(field_value, str) else "Audio"

            # Define field visibility map
            field_map = {
                "Audio": ["audio_image_provider", "openai_api_key", "voice", "audio_format", "speed"],
                "Image": ["audio_image_provider", "openai_api_key", "image_model", "image_size", "num_images"],
                "Video": ["video_provider", "gemini_api_key", "video_model", "aspect_ratio"],
            }

            # Hide all dynamic fields first
            for field_name in [
                "audio_image_provider",
                "video_provider",
                "openai_api_key",
                "gemini_api_key",
                "voice",
                "audio_format",
                "speed",
                "image_model",
                "image_size",
                "num_images",
                "video_model",
                "aspect_ratio",
            ]:
                if field_name in build_config:
                    build_config[field_name]["show"] = False

            # Show fields based on selected output type
            if output_type in field_map:
                for field_name in field_map[output_type]:
                    if field_name in build_config:
                        build_config[field_name]["show"] = True

        elif field_name == "audio_image_provider":
            # For audio and image, always show OpenAI API key
            if field_value == "OpenAI":
                build_config["openai_api_key"]["display_name"] = "OpenAI API Key"
                build_config["openai_api_key"]["info"] = "Your OpenAI API key for generating audio and images"
                build_config["openai_api_key"]["show"] = True
                if "gemini_api_key" in build_config:
                    build_config["gemini_api_key"]["show"] = False

        elif field_name == "video_provider":
            # For video mode, only show gemini_api_key when Google Generative AI is selected
            if field_value == "Google Generative AI":
                if "gemini_api_key" in build_config:
                    build_config["gemini_api_key"]["display_name"] = "Gemini API Key"
                    build_config["gemini_api_key"]["info"] = "Your Google Gemini API key for generating videos with Veo"
                    build_config["gemini_api_key"]["show"] = True

        return build_config

    def _extract_text_from_input(self):
        """Extract text from various input types."""
        input_value = self.input_text[0] if isinstance(self.input_text, list) else self.input_text

        # Handle string input
        if isinstance(input_value, str):
            return input_value

        # Handle Message input
        if hasattr(input_value, "text"):
            return input_value.text

        # Handle Data input
        if hasattr(input_value, "data"):
            if isinstance(input_value.data, dict) and "text" in input_value.data:
                return input_value.data["text"]
            if isinstance(input_value.data, str):
                return input_value.data

        # Handle DataFrame input
        if hasattr(input_value, "to_message"):
            message = input_value.to_message()
            return message.text if hasattr(message, "text") else str(message)

        # Fallback
        return str(input_value)

    def _get_api_key(self):
        """Get API key based on selected provider and output type."""
        # For video generation, always use Gemini API
        if hasattr(self, "output_type") and self.output_type == "Video":
            api_key = self.gemini_api_key
        else:
            # For audio and image, always use OpenAI
            api_key = self.openai_api_key

        if hasattr(api_key, "get_secret_value"):
            return api_key.get_secret_value()
        return str(api_key)

    def generate_audio(self) -> Data:
        """Generate audio from text using OpenAI TTS API."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Data(data={"error": "No text provided for audio generation"})

            api_key = self._get_api_key()
            voice = getattr(self, "voice", "alloy") or "alloy"
            format_ = getattr(self, "audio_format", "mp3") or "mp3"
            speed = getattr(self, "speed", 1) or 1

            url = "https://api.openai.com/v1/audio/speech"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "response_format": format_,
                "speed": float(speed),
            }

            self.status = f"Generating audio with voice '{voice}' in '{format_}' format at speed {speed}x..."
            self.log(f"Making TTS request with voice: {voice}, format: {format_}, speed: {speed}")

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200 and response.content:
                audio_base64 = base64.b64encode(response.content).decode("utf-8")
                audio_size_kb = len(response.content) / 1024

                self.status = f"Audio generated successfully! Size: {audio_size_kb:.1f} KB"
                self.log(f"Audio generated successfully. Size: {len(response.content)} bytes")

                return Data(
                    data={
                        "audio_base64": audio_base64,
                        "format": format_,
                        "voice": voice,
                        "speed": speed,
                        "size_bytes": len(response.content),
                        "text": text[:100] + "..." if len(text) > 100 else text,
                    }
                )
            error_msg = f"API Error {response.status_code}: {response.text}"
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg})

        except Exception as e:
            error_msg = f"Error generating audio: {e!s}"
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg})

    def generate_audio_base64(self) -> Message:
        """Generate audio and return only the base64 as text message."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Message(text="Error: No text provided for audio generation")

            api_key = self._get_api_key()
            voice = getattr(self, "voice", "alloy") or "alloy"
            format_ = getattr(self, "audio_format", "mp3") or "mp3"
            speed = getattr(self, "speed", 1) or 1

            url = "https://api.openai.com/v1/audio/speech"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "response_format": format_,
                "speed": float(speed),
            }

            self.status = f"Generating audio with voice '{voice}' in '{format_}' format at speed {speed}x..."
            self.log(f"Making TTS request with voice: {voice}, format: {format_}, speed: {speed}")

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200 and response.content:
                audio_base64 = base64.b64encode(response.content).decode("utf-8")
                audio_size_kb = len(response.content) / 1024

                self.status = f"Audio generated successfully! Size: {audio_size_kb:.1f} KB"
                self.log(f"Audio generated successfully. Size: {len(response.content)} bytes")

                return Message(text=audio_base64)
            error_msg = f"API Error {response.status_code}: {response.text}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

        except Exception as e:
            error_msg = f"Error generating audio: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def generate_markdown(self) -> Message:
        """Generate markdown output based on the selected output type."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Message(text="Error: No text provided for markdown generation")

            output_type = getattr(self, "output_type", "Audio") or "Audio"

            if output_type == "Audio":
                return self._generate_audio_markdown(text)
            if output_type == "Image":
                return self._generate_image_markdown(text)
            if output_type == "Video":
                return self._generate_video_markdown(text)
            return Message(text="Error: Unknown output type")

        except Exception as e:
            error_msg = f"Error generating markdown: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def _generate_audio_markdown(self, text: str) -> Message:
        """Generate HTML audio player code for the generated audio."""
        try:
            api_key = self._get_api_key()
            voice = getattr(self, "voice", "alloy") or "alloy"
            format_ = getattr(self, "audio_format", "mp3") or "mp3"
            speed = getattr(self, "speed", 1) or 1

            url = "https://api.openai.com/v1/audio/speech"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "response_format": format_,
                "speed": float(speed),
            }

            self.status = f"Generating audio with voice '{voice}' in '{format_}' format at speed {speed}x..."
            self.log(f"Making TTS request with voice: {voice}, format: {format_}, speed: {speed}")

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200 and response.content:
                audio_base64 = base64.b64encode(response.content).decode("utf-8")
                audio_size_kb = len(response.content) / 1024

                self.status = f"Audio generated successfully! Size: {audio_size_kb:.1f} KB"
                self.log(f"Audio generated successfully. Size: {len(response.content)} bytes")

                # Generate HTML audio player code
                html_code = f'<audio controls>\n  <source src="data:audio/{format_};base64,{audio_base64}" type="audio/{format_}">\n</audio>'

                return Message(text=html_code)
            error_msg = f"API Error {response.status_code}: {response.text}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

        except Exception as e:
            error_msg = f"Error generating audio markdown: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def _generate_image_markdown(self, text: str) -> Message:
        """Generate markdown image code for the generated image."""
        try:
            # Check if only one image is requested
            n = getattr(self, "num_images", 1) or 1
            if n != 1:
                return Message(
                    text="Markdown Image output is only available when generating a single image (Number of Images = 1)"
                )

            api_key = self._get_api_key()
            model = getattr(self, "image_model", "dall-e-3") or "dall-e-3"
            size = getattr(self, "image_size", "1024x1024") or "1024x1024"

            client = OpenAI(api_key=api_key)

            self.status = f"Generating image using {model} model..."
            self.log(f"Making image generation request with model: {model}, size: {size}, count: {n}")

            response = client.images.generate(model=model, prompt=text, n=n, size=size)

            # Return markdown image code for the first image
            if response.data and len(response.data) > 0:
                image_url = response.data[0].url
                # Create a description from the prompt
                description = text[:50] + "..." if len(text) > 50 else text
                markdown_code = f"![{description}]({image_url})"

                self.status = "Generated image markdown successfully!"
                self.log(f"Generated image markdown: {markdown_code}")

                return Message(text=markdown_code)
            error_msg = "No image URL generated"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

        except Exception as e:
            error_msg = f"Error generating image markdown: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def _generate_video_markdown(self, text: str) -> Message:
        """Generate HTML video player code for the generated video."""
        try:
            # First, generate the video using the main method
            video_result = self.generate_video()

            # Check if video generation was successful
            if hasattr(video_result, "data") and isinstance(video_result.data, dict):
                if "error" in video_result.data:
                    return Message(text=f"Error: {video_result.data['error']}")

                # Get the primary video URL
                video_url = video_result.data.get("video_url")
                if not video_url:
                    return Message(text="Error: No video URL generated")

                # Determine aspect ratio for dimensions
                aspect_ratio = getattr(self, "aspect_ratio", "16:9") or "16:9"
                if aspect_ratio == "16:9":
                    width, height = 640, 360
                elif aspect_ratio == "9:16":
                    width, height = 360, 640
                else:
                    width, height = 640, 360  # Default to 16:9

                # Generate HTML video player code
                html_code = (
                    f'<video width="{width}" height="{height}" controls>\n  <source src="{video_url}">\n</video>'
                )

                self.status = f"Generated video HTML for {aspect_ratio} aspect ratio"
                return Message(text=html_code)
            return Message(text="Error: Invalid video generation result")

        except Exception as e:
            error_msg = f"Error generating video markdown: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def generate_image(self) -> Data:
        """Generate image from text using OpenAI DALL-E API."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Data(data={"error": "No text provided for image generation"})

            api_key = self._get_api_key()
            model = getattr(self, "image_model", "dall-e-3") or "dall-e-3"
            size = getattr(self, "image_size", "1024x1024") or "1024x1024"
            n = getattr(self, "num_images", 1) or 1

            client = OpenAI(api_key=api_key)

            self.status = f"Generating image using {model} model..."
            self.log(f"Making image generation request with model: {model}, size: {size}, count: {n}")

            response = client.images.generate(model=model, prompt=text, n=n, size=size)

            image_urls = [data.url for data in response.data]
            self.status = f"Generated {len(image_urls)} image(s) successfully!"
            self.log(f"Generated {len(image_urls)} images")

            # Se apenas uma imagem foi gerada, retornar a URL diretamente
            if n == 1 and len(image_urls) == 1:
                return Data(
                    data={
                        "image_url": image_urls[0],
                        "model": model,
                        "size": size,
                        "count": n,
                        "prompt": text[:100] + "..." if len(text) > 100 else text,
                    }
                )
            return Data(
                data={
                    "image_urls": image_urls,
                    "model": model,
                    "size": size,
                    "count": n,
                    "prompt": text[:100] + "..." if len(text) > 100 else text,
                }
            )

        except Exception as e:
            error_msg = f"Error generating image: {e!s}"
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg})

    def generate_image_url(self) -> Message:
        """Generate image and return only the URL as text message."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Message(text="Error: No text provided for image generation")

            api_key = self._get_api_key()
            model = getattr(self, "image_model", "dall-e-3") or "dall-e-3"
            size = getattr(self, "image_size", "1024x1024") or "1024x1024"
            n = getattr(self, "num_images", 1) or 1

            client = OpenAI(api_key=api_key)

            self.status = f"Generating image using {model} model..."
            self.log(f"Making image generation request with model: {model}, size: {size}, count: {n}")

            response = client.images.generate(model=model, prompt=text, n=n, size=size)

            # Return only the first image URL as text
            if response.data and len(response.data) > 0:
                image_url = response.data[0].url
                self.status = "Generated image URL successfully!"
                self.log(f"Generated image URL: {image_url}")

                return Message(text=image_url)
            error_msg = "No image URL generated"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

        except Exception as e:
            error_msg = f"Error generating image URL: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")

    def generate_video(self) -> Data:
        """Generate video from text using Google Veo."""
        try:
            text = self._extract_text_from_input()
            if not text or not text.strip():
                return Data(data={"error": "No text provided for video generation"})

            return self._generate_video_with_veo(text)

        except Exception as e:
            error_msg = f"Error generating video: {e!s}"
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg})

    def _generate_video_with_veo(self, text: str) -> Data:
        """Generate video using Google Veo."""
        try:
            api_key = self._get_api_key()
            model = getattr(self, "video_model", "veo-3.0-generate-preview") or "veo-3.0-generate-preview"
            aspect_ratio = getattr(self, "aspect_ratio", "16:9") or "16:9"

            # Create client with API key
            client = genai.Client(api_key=api_key)

            self.status = f"Generating video using {model} model..."
            self.log(f"Making video generation request with model: {model}, aspect_ratio: {aspect_ratio}")

            # Generate video using the selected model
            operation = client.models.generate_videos(
                model=model,
                prompt=text,
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect_ratio,
                ),
            )

            self.status = f"Waiting for video generation completion using {model}..."

            # Poll for completion with proper interval (20 seconds as per documentation)
            while not operation.done:
                time.sleep(20)
                operation = client.operations.get(operation)

            # Process generated videos
            video_urls = []
            video_data = []

            for n, generated_video in enumerate(operation.response.generated_videos):
                if hasattr(generated_video, "video") and generated_video.video:
                    video_info = {"video_id": n, "video_object": generated_video.video}

                    # Add URI if available (needs API key appended for download)
                    if hasattr(generated_video.video, "uri"):
                        video_url = f"{generated_video.video.uri}&key={api_key}"
                        video_info["video_uri"] = video_url
                        video_urls.append(video_url)

                    video_data.append(video_info)

            if not video_data:
                raise ValueError("No video was generated.")

            self.status = f"Video(s) generated successfully using {model}. Total: {len(video_data)}"

            # Return the first video URL as main output, with detailed data available
            primary_video_url = video_urls[0] if video_urls else None

            return Data(
                data={
                    "video_url": primary_video_url,  # Direct link to first video
                    "video_urls": video_urls,  # List of all links
                    "video_count": len(video_data),
                    "videos": video_data,  # Complete data
                    "model_used": model,  # Model used
                    "prompt_used": text,
                    "aspect_ratio": aspect_ratio,
                    "provider": "Gemini",
                }
            )

        except Exception as e:
            error_message = str(e)
            self.status = f"Error with model {model}: {error_message}"

            # Provide helpful error info
            return Data(
                data={
                    "error": error_message,
                    "model_attempted": model,
                    "video_count": 0,
                    "provider": "Gemini",
                    "suggestion": "Try using veo-3.0-generate-preview for the latest model, or check your API key and billing setup",
                }
            )

    def generate_video_urls(self) -> Message:
        """Generate video and return only the URLs as text message."""
        try:
            # First, generate the video using the main method
            video_result = self.generate_video()

            # Check if video generation was successful
            if hasattr(video_result, "data") and isinstance(video_result.data, dict):
                if "error" in video_result.data:
                    return Message(text=f"Error: {video_result.data['error']}")

                # Get video URLs
                video_urls = video_result.data.get("video_urls", [])
                if not video_urls:
                    return Message(text="Error: No video URLs generated")

                # Return URLs as comma-separated text
                urls_text = ", ".join(video_urls)
                self.status = f"Generated {len(video_urls)} video URL(s) successfully!"
                return Message(text=urls_text)
            return Message(text="Error: Invalid video generation result")

        except Exception as e:
            error_msg = f"Error generating video URLs: {e!s}"
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")
