import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FileInput, MultilineInput, SecretStrInput
from lfx.schema import Message
from lfx.template import Output

HTTP_BAD_REQUEST = 400


class AnymizeComponent(Component):
    display_name: str = "anymize"
    description: str = (
        "Securely anonymize and de-anonymize text and documents using anymize.ai's GDPR-compliant AI service. "
        "Protects personal data before sending to LLMs and other AI services."
    )
    documentation: str = "https://explore.anymize.ai/api-docs"
    icon: str = "eye-off"
    priority: int = 100
    name: str = "anymize"

    inputs = [
        SecretStrInput(
            name="anymize_api",
            display_name="anymize API Key",
            info=(
                "Your anymize.ai API key for authentication. Get your API key from "
                "https://anymize.ai after creating an account. Required for all operations."
            ),
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["anonymize_text", "deanonymize_text", "file_anonymization"],
            value="anonymize_text",
            real_time_refresh=True,
            info="Select operation: anonymize text to hashes, deanonymize hashes to text, or process files via OCR.",
        ),
        MultilineInput(
            name="text",
            display_name="Text Input",
            dynamic=True,
            show=True,
            info="Input text containing personal data to anonymize or hash-coded text to de-anonymize.",
        ),
        FileInput(
            name="file",
            display_name="File Input",
            dynamic=True,
            show=False,
            info="Upload documents (PDF, images, scans) for OCR processing and anonymization.",
            file_types=["pdf", "png", "jpg", "gif", "bmp", "txt", "doc", "docx"],
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            options=["en", "de", "fr", "es", "it"],
            value="en",
            dynamic=True,
            show=True,
        ),
    ]
    outputs = [Output(name="process", display_name="Process", method="process")]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "operation":
            build_config.setdefault("text", {})["show"] = field_value in {"anonymize_text", "deanonymize_text"}
            build_config.setdefault("language", {})["show"] = field_value in {"anonymize_text"}
            build_config.setdefault("file", {})["show"] = field_value == "file_anonymization"
        return build_config

    def _pre_run_setup(self):
        if hasattr(self, "operation") and not self.operation:
            self.operation = "anonymize_text"

        build_config = getattr(self, "_build_config", {})
        build_config.setdefault("text", {})["show"] = True
        build_config.setdefault("language", {})["show"] = True
        build_config.setdefault("file", {})["show"] = False
        self._build_config = build_config

    async def process(self) -> Message:
        try:
            if self.operation == "anonymize_text":
                if not self.text:
                    return Message(text="Error: No text provided for anonymization.")

                response = await self._anonymize_text(self.text, self.language)

                if "job_id" not in response:
                    return Message(text=f"Error: Failed to start anonymization job. Response: {response}")

                job_id = response["job_id"]
                final_response = await self._poll_status(job_id)

                if "anonymized_text_raw" in final_response:
                    return Message(text=final_response["anonymized_text_raw"])
                return Message(text=f"Anonymization completed but no anonymized text found. Response: {final_response}")

            if self.operation == "deanonymize_text":
                if not self.text:
                    return Message(text="Error: No text provided for deanonymization.")

                response = await self._deanonymize_text(self.text)

                if "text" in response:
                    return Message(text=response["text"])
                return Message(text=f"Deanonymization failed. Response: {response}")

            if self.operation == "file_anonymization":
                if not self.file:
                    return Message(text="Error: No file provided for anonymization.")

                response = await self._anonymize_file(self.file)

                if "job_id" not in response:
                    return Message(text=f"Error: Failed to start file anonymization job. Response: {response}")

                job_id = response["job_id"]

                final_response = await self._poll_status(job_id)

                if "anonymized_text_raw" in final_response:
                    return Message(text=final_response["anonymized_text_raw"])
                return Message(
                    text=f"File anonymization completed but no anonymized text found. Response: {final_response}"
                )
            return Message(text=f"Error: Unknown operation '{self.operation}'")
        except (RuntimeError, ValueError, TypeError, asyncio.TimeoutError) as e:
            return Message(text=f"Error during processing: {e!s}")

    async def _anonymize_file(self, file_input) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.anymize_api}"}

        if isinstance(file_input, str):
            file_path = file_input
            file_name = Path(file_path).name
        elif hasattr(file_input, "path"):
            file_path = file_input.path
            file_name = getattr(file_input, "name", Path(file_path).name)
        else:
            msg = "Invalid file_input type"
            raise TypeError(msg)

        timeout = aiohttp.ClientTimeout(total=300)

        with Path(file_path).open("rb") as f:  # ruff: noqa: ASYNC230
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = aiohttp.FormData()
                data.add_field("file", f, filename=file_name)

                async with session.post(
                    "https://app.anymize.ai/api/ocr",
                    headers=headers,
                    data=data,
                ) as response:
                    if response.status >= HTTP_BAD_REQUEST:
                        text = await response.text()
                        error_msg = f"anymize API error {response.status}: {text[:200]}"
                        raise RuntimeError(error_msg)
                    return await response.json()

    async def _anonymize_text(self, text: str, language: str = "en") -> dict[str, Any]:
        body = {
            "text": text,
            "language": language,
        }

        return await self._anymize_api_request("POST", "/api/anonymize", body)

    async def _get_anonymization_status(self, job_id: str) -> dict[str, Any]:
        return await self._anymize_api_request("GET", f"/api/status/{job_id}")

    async def _deanonymize_text(self, text: str) -> dict[str, Any]:
        body = {
            "text": text,
        }

        return await self._anymize_api_request("POST", "/api/deanonymize", body)

    async def _anymize_api_request(
        self,
        method: str,
        resource: str,
        body: dict[str, Any] | None = None,
        qs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.anymize_api}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url = f"https://app.anymize.ai{resource}"
        body = {} if body is None else body
        qs = {} if qs is None else qs
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if method == "POST":
                async with session.post(url, headers=headers, json=body, params=qs) as response:
                    if response.status >= HTTP_BAD_REQUEST:
                        text = await response.text()
                        error_msg = f"anymize API error {response.status}: {text[:200]}"
                        raise RuntimeError(error_msg)
                    return await response.json()
            elif method == "GET":
                async with session.get(url, headers=headers, params=qs) as response:
                    if response.status >= HTTP_BAD_REQUEST:
                        text = await response.text()
                        error_msg = f"API error {response.status}"
                        raise RuntimeError(error_msg)
                    return await response.json()
            else:
                error_msg = f"Unsupported method: {method}"
                raise ValueError(error_msg)

    async def _poll_status(
        self,
        job_id: str,
        max_retries: int = 150,
        retry_interval: int = 10000,
        error_message: str = "Anonymization timeout: Process did not complete within expected time",
    ) -> dict[str, Any]:
        for _ in range(max_retries):
            response = await self._get_anonymization_status(job_id)
            if response["status"] == "completed":
                return response
            await asyncio.sleep(retry_interval / 1000)

        raise RuntimeError(error_message)
