import base64
import mimetypes
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from langchain_core.tools import StructuredTool
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DropdownInput, MultilineInput, SecretStrInput
from langflow.schema import Data
from langflow.utils.util_strings import to_pythonic_variable_name

DALL_E_PARAMS = {
    "dall-e-2": {
        "result_format": ["url", "file", "base64_json", "base64"],
        "size": ["256x256", "512x512", "1024x1024"],
        "quality": ["standard"],
    },
    "dall-e-3": {
        "result_format": ["url", "file", "base64_json", "base64"],
        "size": ["1024x1024", "1024x1792", "1792x1024"],
        "quality": ["standard", "hd"],
    },
}
DEFAULT_MODEL = "dall-e-3"


class DallESchema(BaseModel):
    prompt: str = Field(..., description="Image generation prompt")


class DallEWrapper(BaseModel):
    client: OpenAI
    dall_e_model: str
    result_format: str
    size: str
    quality: str

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _args(self, prompt: str) -> dict[str, Any]:
        if self.result_format in ["base64", "base64_json"]:
            response_format = "b64_json"
        elif self.result_format == "file":
            response_format = "url"
        else:
            response_format = self.result_format

        return {
            "model": self.dall_e_model,
            "prompt": prompt,
            "response_format": response_format,
            "size": self.size,
            "quality": self.quality,
            "n": 1,
        }

    def run(self, prompt: str) -> dict[str, Any]:
        args = self._args(prompt)
        response = self.client.images.generate(**args)

        if response and response.data:
            image_data = response.data[0]
            if self.result_format in ["base64", "base64_json"] and hasattr(image_data, "b64_json"):
                if self.result_format == "base64":
                    result = base64.b64decode(image_data.b64_json)
                else:
                    result = image_data.b64_json
            elif self.result_format in ["file", "url"] and hasattr(image_data, "url"):
                if self.result_format == "url":  # noqa: SIM108
                    result = image_data.url
                else:
                    result = str(self._download(image_data.url))
            else:
                msg = "Unexpected image format in response data."
                raise ValueError(msg)
        else:
            msg = "No response from OpenAI DALL-E API."
            raise ValueError(msg)

        return {
            "result": result,
            "result_format": self.result_format,
            "prompt": prompt,
        }

    def _download(self, url: str, response: httpx.Response | None = None) -> Path:
        temp_dir = Path(tempfile.gettempdir()) / self.__class__.__name__
        temp_dir.mkdir(parents=True, exist_ok=True)

        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

        # Determine content type and infer the file extension
        content_type = response.headers.get("Content-Type", "")
        extension = mimetypes.guess_extension(content_type.split(";")[0]) if content_type else None
        if not extension:
            extension = ".bin"

        # Generate a unique filename
        unique_id = response.headers.get("Content-MD5") or response.headers.get("ETag", "").strip('"')
        if unique_id:
            filename = f"{unique_id}{extension}"
        else:
            # Fall back to a timestamp-based unique name
            timestamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d%H%M%S%f")
            filename = f"{timestamp}{extension}"

        # Define the full file path
        file_path = temp_dir / filename

        # Save the content to the file
        with file_path.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

        return file_path


class DallEComponent(LCToolComponent):
    display_name = "DALL-E"
    description = "Generate Images with OpenAI DALL-E."
    name = "DallETool"
    icon = "OpenAI"

    inputs = [
        MultilineInput(
            name="prompt",
            display_name="Image Prompt",
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            required=True,
            info="The OpenAI API Key to use for the OpenAI model.",
            value="OPENAI_API_KEY",
        ),
        DropdownInput(
            name="dall_e_model",
            display_name="Model Name",
            required=True,
            options=list(DALL_E_PARAMS.keys()),
            value=DEFAULT_MODEL,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="result_format",
            display_name="Output Format",
            options=DALL_E_PARAMS[DEFAULT_MODEL]["result_format"],
            value=DALL_E_PARAMS[DEFAULT_MODEL]["result_format"][0],
        ),
        DropdownInput(
            name="size",
            display_name="Image Size",
            options=DALL_E_PARAMS[DEFAULT_MODEL]["size"],
            value=DALL_E_PARAMS[DEFAULT_MODEL]["size"][0],
        ),
        DropdownInput(
            name="quality",
            display_name="Image Quality",
            options=DALL_E_PARAMS[DEFAULT_MODEL]["quality"],
            value=DALL_E_PARAMS[DEFAULT_MODEL]["quality"][0],
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "dall_e_model":
            new_model = field_value

            build_config["result_format"]["options"] = DALL_E_PARAMS[new_model]["result_format"]
            build_config["size"]["options"] = DALL_E_PARAMS[new_model]["size"]
            build_config["quality"]["options"] = DALL_E_PARAMS[new_model]["quality"]

            # Reset invalid values
            for field in ["result_format", "size", "quality"]:
                if build_config[field]["value"] not in build_config[field]["options"]:
                    build_config[field]["value"] = DALL_E_PARAMS[new_model][field][0]

        return build_config

    def build_tool(self) -> Tool:
        client = OpenAI(api_key=self.api_key)

        wrapper = self._build_wrapper(
            client=client,
            dall_e_model=self.dall_e_model,
            result_format=self.result_format,
            size=self.size,
            quality=self.quality,
        )

        tool = StructuredTool.from_function(
            name=to_pythonic_variable_name(self.effective_display_name),
            description=self.effective_description,
            func=wrapper.run,
            args_schema=DallESchema,
        )

        self.status = tool.description
        return tool

    def run_model(self) -> Data:
        tool = self.build_tool()

        results = tool.run(self.prompt)

        if self.result_format == "file":
            data = Data(
                file_path=results["result"],
                text=results["prompt"],
            )
        else:
            data = Data(
                result=results["result"],
                result_format=results["result_format"],
                text=results["prompt"],
            )

        self.status = data

        return data

    def _build_wrapper(
        self,
        client: OpenAI,
        dall_e_model: str,
        result_format: str,
        size: str,
        quality: str,
    ) -> DallEWrapper:
        return DallEWrapper(
            client=client,
            dall_e_model=dall_e_model,
            result_format=result_format,
            size=size,
            quality=quality,
        )
