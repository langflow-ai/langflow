from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data


class JigsawStackImageGenerationComponent(Component):
    display_name = "Image Generation"
    description = "Generate an image based on the given text by employing AI models like Flux, \
        Stable Diffusion, and other top models."
    documentation = "https://jigsawstack.com/docs/api-reference/ai/image-generation"
    icon = "JigsawStack"
    name = "JigsawStackImageGeneration"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="The text prompt to generate the image from. Must be between 1-5000 characters.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            info="The aspect ratio of the generated image. Must be one of the following:\
                '1:1', '16:9', '21:9', '3:2', '2:3', '4:5', '5:4', '3:4', '4:3', '9:16', '9:21' \
                Default is 1:1.",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="A valid URL where the generated image will be sent.",
            required=False,
        ),
        MessageTextInput(
            name="file_store_key",
            display_name="File Store Key",
            info="The key used to store the image on Jigsawstack File Storage. Not required if url is specified.",
            required=False,
            tool_mode=True,
        ),
        IntInput(
            name="width",
            display_name="Width",
            info="The width of the image. Must be between 256-1920 pixels.",
            required=False,
        ),
        IntInput(
            name="height",
            display_name="Height",
            info="The height of the image. Must be between 256-1920 pixels.",
            required=False,
        ),
        IntInput(
            name="steps",
            display_name="Steps",
            info="The number of denoising steps. Must be between 1-90. \
                Higher values produce better quality images but take more time to generate.",
            required=False,
        ),
        DropdownInput(
            name="output_format",
            display_name="Output Format",
            info="The output format of the generated image. Must be one of the following values:\
                png or svg",
            required=False,
            options=["png", "svg"],
            value="png",
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="The text prompt to avoid in the generated image. \
                Must be between 1-5000 characters.",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Makes generation deterministic.\
                Using the same seed and set of parameters will produce identical image each time.",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
        IntInput(
            name="guidance",
            display_name="Guidance Scale",
            info="Higher guidance forces the model to better follow the prompt, \
                but may result in lower quality output. Must be between 1-28.",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Image Generation Results", name="image_generation_results", method="generate_image"),
    ]

    def generate_image(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            min_character_length = 1
            max_character_length = 5000
            min_width = 256
            max_width = 1920
            min_height = 256
            max_height = 1920
            min_steps = 1
            max_steps = 90
            client = JigsawStack(api_key=self.api_key)

            if not self.prompt or len(self.prompt) < min_character_length or len(self.prompt) > max_character_length:
                invalid_prompt_error = f"Prompts must be between \
                    {min_character_length}-{max_character_length} characters."
                raise ValueError(invalid_prompt_error)

            if self.aspect_ratio and self.aspect_ratio not in [
                "1:1",
                "16:9",
                "21:9",
                "3:2",
                "2:3",
                "4:5",
                "5:4",
                "3:4",
                "4:3",
                "9:16",
                "9:21",
            ]:
                invalid_aspect_ratio_error = (
                    "Aspect ratio must be one of the following: '1:1', '16:9', '21:9', '3:2', '2:3', "
                    "'4:5', '5:4', '3:4', '4:3', '9:16', '9:21'."
                )
                raise ValueError(invalid_aspect_ratio_error)
            if self.width and (self.width < min_width or self.width > max_width):
                invalid_width_error = f"Width must be between {min_width}-{max_width} pixels."
                raise ValueError(invalid_width_error)
            if self.height and (self.height < min_height or self.height > max_height):
                invalid_height_error = f"Height must be between {min_height}-{max_height} pixels."
                raise ValueError(invalid_height_error)
            if self.steps and (self.steps < min_steps or self.steps > max_steps):
                invalid_steps_error = f"Steps must be between {min_steps}-{max_steps}."
                raise ValueError(invalid_steps_error)

            params = {}
            if self.prompt:
                params["prompt"] = self.prompt.strip()
            if self.aspect_ratio:
                params["aspect_ratio"] = self.aspect_ratio.strip()
            if self.url:
                params["url"] = self.url.strip()
            if self.file_store_key:
                params["file_store_key"] = self.file_store_key.strip()
            if self.width:
                params["width"] = self.width
            if self.height:
                params["height"] = self.height
            params["return_type"] = "url"
            if self.output_format:
                params["output_format"] = self.output_format.strip()
            if self.steps:
                params["steps"] = self.steps

            # Initialize advance_config if any advanced parameters are provided
            if self.negative_prompt or self.seed or self.guidance:
                params["advance_config"] = {}
            if self.negative_prompt:
                params["advance_config"]["negative_prompt"] = self.negative_prompt
            if self.seed:
                params["advance_config"]["seed"] = self.seed
            if self.guidance:
                params["advance_config"]["guidance"] = self.guidance

            # Call image generation
            response = client.image_generation(params)

            if response.get("url", None) is None or response.get("url", None).strip() == "":
                failed_response_error = "JigsawStack API returned unsuccessful response"
                raise ValueError(failed_response_error)

            return Data(data=response)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
