from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING, Any

import httpx
from lfx.base.data.base_file import BaseFileComponent
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.ssrf_protection import is_ssrf_protection_enabled, validate_and_resolve_connector_url
from lfx.utils.ssrf_transport import create_ssrf_protected_sync_client, pin_host_for_url

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

IMAGE_MIME_BY_EXTENSION = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "webp": "image/webp",
}

# MiniCPM-OCR's own client sends the image before the prompt and passes these
# slice arguments to vLLM/SGLang. They control how a high-resolution page is
# split before recognition, so omitting them lowers OCR quality on dense pages.
MINICPM_SLICE_ARGS = {"max_slice_nums": 9, "downsample_mode": "4x"}


class MiniCPMOCRComponent(BaseFileComponent):
    """OCR images and scanned PDFs with a self-hosted MiniCPM-OCR model."""

    display_name = "MiniCPM OCR"
    description = "Extract text from images and scanned PDFs with a self-hosted MiniCPM-OCR model."
    documentation = "https://github.com/OpenBMB/MiniCPM-OCR"
    icon = "file-search"

    VALID_EXTENSIONS = ["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp", "pdf"]
    DEFAULT_BASE_URL = "http://127.0.0.1:8000"
    DEFAULT_MODEL = "minicpm-ocr"
    DEFAULT_PROMPT = "Text Recognition:"
    CHAT_PATH = "/v1/chat/completions"
    REQUEST_TIMEOUT = 120
    PDF_RENDER_DPI = 200

    inputs = [
        *BaseFileComponent.get_base_inputs(),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            required=False,
            value=DEFAULT_BASE_URL,
            info=(
                "Base URL of the OpenAI-compatible MiniCPM-OCR server, for example "
                "http://127.0.0.1:8000 for vLLM or http://localhost:11434 for Ollama. "
                "Do not include /v1; the component appends it."
            ),
        ),
        MessageTextInput(
            name="model",
            display_name="Model",
            required=False,
            value=DEFAULT_MODEL,
            advanced=True,
            info="Model name served by the MiniCPM-OCR endpoint.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=False,
            password=True,
            advanced=True,
            info="Optional API key sent as a Bearer token. Self-hosted servers often need none.",
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=False,
            value=DEFAULT_PROMPT,
            advanced=True,
            info="Instruction sent with every page. Use 'Table Recognition:' for table-heavy pages.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            required=False,
            value=REQUEST_TIMEOUT,
            advanced=True,
            info="Timeout in seconds for one page recognition request.",
        ),
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        if not file_list:
            self.log("No files to process.")
            return file_list

        base_url = self._normalize_base_url(self.base_url or self.DEFAULT_BASE_URL)
        prompt = str(self.prompt or "").strip() or self.DEFAULT_PROMPT
        timeout = self._resolve_timeout()
        headers = {"Content-Type": "application/json"}
        api_key = str(self.api_key or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # The endpoint is configured by the flow author, so it follows the
        # connector SSRF policy: loopback is allowed by default while private
        # ranges and metadata targets stay blocked, and non-exempt hosts are
        # DNS-pinned for the rest of the run.
        _validated_url, base_ips = validate_and_resolve_connector_url(base_url)
        endpoint = f"{base_url}{self.CHAT_PATH}"

        with self._build_client(base_url, base_ips, timeout) as client:
            for file in file_list:
                try:
                    file.data = self._process_file(
                        client=client,
                        endpoint=endpoint,
                        headers=headers,
                        file_path=file.path,
                        prompt=prompt,
                        timeout=timeout,
                    )
                except Exception as error:
                    message = f"MiniCPM-OCR failed for {file.path.name}: {error}"
                    self.log(message)
                    raise RuntimeError(message) from error

        return file_list

    def _process_file(
        self,
        *,
        client: httpx.Client,
        endpoint: str,
        headers: dict[str, str],
        file_path: Path,
        prompt: str,
        timeout: float,
    ) -> Data:
        pages = list(self._load_pages(file_path))
        if not pages:
            msg = "the file has no pages to recognize"
            raise ValueError(msg)

        text_parts = [
            self._recognize(client, endpoint, headers, image_bytes, mime, prompt, timeout)
            for image_bytes, mime in pages
        ]
        text = "\n\n".join(part for part in text_parts if part)

        return Data(
            text=text,
            data={
                self.SERVER_FILE_PATH_FIELDNAME: str(file_path),
                "text": text,
                "page_count": len(pages),
                "model": str(self.model or self.DEFAULT_MODEL),
                "ocr_engine": "minicpm-ocr",
            },
        )

    def _load_pages(self, file_path: Path) -> Iterator[tuple[bytes, str]]:
        extension = file_path.suffix.lower().lstrip(".")
        if extension == "pdf":
            yield from self._render_pdf(file_path)
            return

        mime = IMAGE_MIME_BY_EXTENSION.get(extension)
        if mime is None:
            msg = f"unsupported file type: {file_path.suffix or '(none)'}"
            raise ValueError(msg)
        yield file_path.read_bytes(), mime

    def _render_pdf(self, file_path: Path) -> Iterator[tuple[bytes, str]]:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(str(file_path))
        try:
            for index in range(len(document)):
                page = document[index]
                bitmap = page.render(scale=self.PDF_RENDER_DPI / 72)
                image = bitmap.to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                yield buffer.getvalue(), "image/png"
        finally:
            document.close()

    def _recognize(
        self,
        client: httpx.Client,
        endpoint: str,
        headers: dict[str, str],
        image_bytes: bytes,
        mime: str,
        prompt: str,
        timeout: float,
    ) -> str:
        image_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

        response = self._post(client, endpoint, headers, image_url, prompt, timeout, with_slice_args=True)
        if response.status_code in (400, 422):
            # Endpoints that do not implement the vLLM/SGLang extension may
            # reject the field with a generic message; retry once without it.
            response = self._post(client, endpoint, headers, image_url, prompt, timeout, with_slice_args=False)

        if response.is_error:
            detail = response.text.strip()[:300]
            msg = f"request failed (HTTP {response.status_code})" + (f": {detail}" if detail else "")
            raise RuntimeError(msg)

        try:
            payload: Any = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            msg = "the endpoint returned an invalid response"
            raise RuntimeError(msg) from error

        if not isinstance(content, str) or not content.strip():
            msg = "the endpoint returned an empty result"
            raise RuntimeError(msg)

        return content.strip()

    def _post(
        self,
        client: httpx.Client,
        endpoint: str,
        headers: dict[str, str],
        image_url: str,
        prompt: str,
        timeout: float,
        *,
        with_slice_args: bool,
    ) -> httpx.Response:
        payload: dict[str, Any] = {
            "model": str(self.model or self.DEFAULT_MODEL),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "stream": False,
        }
        if with_slice_args:
            payload["mm_processor_kwargs"] = MINICPM_SLICE_ARGS

        return client.post(endpoint, headers=headers, json=payload, timeout=timeout)

    def _resolve_timeout(self) -> float:
        raw = self.timeout if self.timeout is not None else self.REQUEST_TIMEOUT
        try:
            timeout = float(raw)
        except (TypeError, ValueError) as error:
            msg = f"Timeout must be a number of seconds, got {raw!r}"
            raise ValueError(msg) from error
        if timeout <= 0:
            msg = f"Timeout must be greater than zero, got {timeout}"
            raise ValueError(msg)
        return timeout

    @staticmethod
    def _normalize_base_url(raw: str) -> str:
        return raw.strip().rstrip("/").removesuffix("/v1")

    def _build_client(self, url: str, validated_ips: list[str], timeout: float) -> httpx.Client:
        """Create the HTTP client, pinning DNS when SSRF protection applies."""
        if is_ssrf_protection_enabled() and validated_ips:
            hostname = pin_host_for_url(url)
            if hostname:
                return create_ssrf_protected_sync_client(
                    hostname=hostname, validated_ips=validated_ips, timeout=timeout
                )
        return httpx.Client(timeout=timeout)
