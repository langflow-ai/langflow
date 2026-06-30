from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
from lfx.base.data.base_file import BaseFileComponent
from lfx.inputs.inputs import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.ssrf_protection import is_ssrf_protection_enabled, validate_and_resolve_url
from lfx.utils.ssrf_transport import create_ssrf_protected_sync_client

if TYPE_CHECKING:
    from pathlib import Path


class PaddleOCRComponent(BaseFileComponent):
    display_name = "PaddleOCR"
    description = "Use PaddleOCR for either layout-aware document parsing into Markdown or plain OCR text recognition."
    documentation = "https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/paddleocr_and_ppstructure.html"
    icon = "file-search"
    name = "PaddleOCR"

    VALID_EXTENSIONS = ["png", "jpg", "jpeg", "bmp", "tiff", "webp", "pdf"]
    DEFAULT_BASE_URL = "https://paddleocr.aistudio-app.com"
    API_PATH = "/api/v2/ocr/jobs"
    REQUEST_TIMEOUT = 300.0
    INITIAL_POLL_INTERVAL = 3.0
    POLL_MULTIPLIER = 1.5
    MAX_POLL_INTERVAL = 15.0

    inputs = [
        *BaseFileComponent.get_base_inputs(),
        SecretStrInput(
            name="access_token",
            display_name="AI Studio Access Token",
            required=True,
            info="AI Studio access token. Get it from https://aistudio.baidu.com/account/accessToken.",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            required=False,
            value="",
            info="Optional PaddleOCR service root URL. Leave empty to use the official default service.",
            advanced=True,
        ),
        DropdownInput(
            name="task_type",
            display_name="Task Type",
            options=["document_parsing", "ocr"],
            value="document_parsing",
            info=(
                "document_parsing: preserves reading order and layout as Markdown — "
                "best when you need structure-aware text (PDFs, scanned documents, tables).\n"
                "ocr: extracts text regions in scan order — best for images with simple text content."
            ),
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["PP-StructureV3", "PaddleOCR-VL-1.6"],
            value="PP-StructureV3",
            info="PaddleOCR model to use for the selected task type.",
        ),
        IntInput(
            name="poll_timeout",
            display_name="Timeout (s)",
            value=600,
            info="Maximum time to wait for the PaddleOCR job to complete.",
            advanced=True,
        ),
        BoolInput(
            name="use_doc_orientation_classify",
            display_name="Document Orientation Classification",
            value=False,
            advanced=True,
            info="OCR/document parsing option. Enable document orientation classification.",
        ),
        BoolInput(
            name="use_doc_unwarping",
            display_name="Document Unwarping",
            value=False,
            advanced=True,
            info="OCR/document parsing option. Enable document unwarping.",
        ),
        BoolInput(
            name="use_textline_orientation",
            display_name="Text Line Orientation",
            value=False,
            advanced=True,
            info="OCR option. Enable text line orientation detection.",
        ),
        FloatInput(
            name="text_det_thresh",
            display_name="Text Detection Threshold",
            required=False,
            advanced=True,
            info="OCR option. Text detection threshold.",
        ),
        FloatInput(
            name="text_det_box_thresh",
            display_name="Text Detection Box Threshold",
            required=False,
            advanced=True,
            info="OCR option. Text detection box threshold.",
        ),
        FloatInput(
            name="text_det_unclip_ratio",
            display_name="Text Detection Unclip Ratio",
            required=False,
            advanced=True,
            info="OCR option. Text detection unclip ratio.",
        ),
        FloatInput(
            name="text_rec_score_thresh",
            display_name="Text Recognition Score Threshold",
            required=False,
            advanced=True,
            info="OCR option. Text recognition score threshold.",
        ),
        BoolInput(
            name="use_table_recognition",
            display_name="Table Recognition",
            value=True,
            advanced=True,
            info="Document parsing option. Enable table recognition.",
        ),
        BoolInput(
            name="use_formula_recognition",
            display_name="Formula Recognition",
            value=False,
            advanced=True,
            info="Document parsing option. Enable formula recognition.",
        ),
        BoolInput(
            name="use_chart_recognition",
            display_name="Chart Recognition",
            value=False,
            advanced=True,
            info="Document parsing option. Enable chart recognition.",
        ),
        BoolInput(
            name="use_seal_recognition",
            display_name="Seal Recognition",
            value=False,
            advanced=True,
            info="Document parsing option. Enable seal recognition.",
        ),
        BoolInput(
            name="prettify_markdown",
            display_name="Prettify Markdown",
            value=True,
            advanced=True,
            info="Document parsing option. Return prettier Markdown when supported.",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            required=False,
            advanced=True,
            info="PaddleOCR-VL option. Sampling temperature.",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            required=False,
            advanced=True,
            info="PaddleOCR-VL option. Nucleus sampling top_p.",
        ),
        BoolInput(
            name="visualize",
            display_name="Visualize",
            value=False,
            advanced=True,
            info="Document parsing option. Generate visualization outputs when supported.",
        ),
    ]

    outputs = [*BaseFileComponent.get_base_outputs()]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "task_type":
            if field_value == "ocr":
                build_config["model"]["options"] = ["PP-OCRv6", "PP-OCRv5"]
                build_config["model"]["value"] = "PP-OCRv6"
            else:
                build_config["model"]["options"] = ["PP-StructureV3", "PaddleOCR-VL-1.6"]
                build_config["model"]["value"] = "PP-StructureV3"

        return build_config

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        if not file_list:
            self.log("No files to process.")
            return file_list

        access_token = str(self.access_token or "").strip()
        if not access_token:
            msg = "AI Studio Access Token is required."
            raise ValueError(msg)

        base_url = (str(self.base_url or "").strip() or self.DEFAULT_BASE_URL).rstrip("/")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Platform": "langflow",
        }
        poll_timeout = int(self.poll_timeout or 600)

        # ``base_url`` is operator-configurable, so the submit and poll requests
        # (which carry the bearer token and the uploaded file) are validated for
        # SSRF up front and DNS-pinned for the rest of the run.  Like
        # ``_fetch_result``, this is a no-op when SSRF protection is disabled
        # (the default), so default behavior is unchanged.
        _validated_url, base_ips = validate_and_resolve_url(base_url)

        try:
            for file in file_list:
                file.data = self._process_file(file.path, base_url, base_ips, headers, poll_timeout)
        except Exception as e:
            error_message = self._format_paddleocr_error(e)
            self.log(error_message)
            raise RuntimeError(error_message) from e

        return file_list

    def _process_file(
        self, file_path: Path, base_url: str, base_ips: list[str], headers: dict[str, str], poll_timeout: int
    ) -> Data:
        options = self._build_ocr_options() if self.task_type == "ocr" else self._build_document_parsing_options()
        job_id = self._submit_job(
            base_url=base_url, base_ips=base_ips, headers=headers, file_path=file_path, options=options
        )
        jsonl_data = self._poll_job(
            base_url=base_url, base_ips=base_ips, headers=headers, job_id=job_id, poll_timeout=poll_timeout
        )

        if self.task_type == "ocr":
            return self._ocr_result_to_data(job_id, jsonl_data, file_path)
        return self._document_result_to_data(job_id, jsonl_data, file_path)

    def _submit_job(
        self, *, base_url: str, base_ips: list[str], headers: dict[str, str], file_path: Path, options: dict[str, Any]
    ) -> str:
        url = f"{base_url}{self.API_PATH}"
        data = {"model": self.model, "optionalPayload": json.dumps(options)}
        with (
            file_path.open("rb") as file_obj,
            self._build_client(url, base_ips) as client,
        ):
            response = client.post(
                url,
                data=data,
                files={"file": (file_path.name, file_obj)},
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
            )
        response.raise_for_status()
        payload = response.json()
        job_id = (payload.get("data") or {}).get("jobId") or payload.get("jobId")
        if not job_id:
            msg = f"PaddleOCR job ID not found in response: {payload}"
            raise ValueError(msg)
        return job_id

    def _poll_job(
        self,
        *,
        base_url: str,
        base_ips: list[str],
        headers: dict[str, str],
        job_id: str,
        poll_timeout: int,
    ) -> list[dict[str, Any]]:
        status_url = f"{base_url}{self.API_PATH}/{job_id}"
        deadline = time.monotonic() + poll_timeout
        interval = self.INITIAL_POLL_INTERVAL

        with self._build_client(status_url, base_ips) as client:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    msg = f"PaddleOCR job {job_id} timed out."
                    raise TimeoutError(msg)

                # Bound each request by the remaining budget so a hung poll cannot
                # overrun ``poll_timeout`` by up to ``REQUEST_TIMEOUT``.
                response = client.get(status_url, headers=headers, timeout=min(self.REQUEST_TIMEOUT, remaining))
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data") or {}
                state = data.get("state") or payload.get("state")

                if state == "done":
                    result_url = data.get("resultJsonUrl") or (data.get("resultUrl") or {}).get("jsonUrl")
                    if not result_url:
                        msg = f"PaddleOCR result URL not found in response: {payload}"
                        raise ValueError(msg)
                    return self._fetch_result(result_url)

                if state == "failed":
                    msg = f"PaddleOCR job failed: {payload}"
                    raise RuntimeError(msg)

                time.sleep(min(interval, max(deadline - time.monotonic(), 0)))
                interval = min(interval * self.POLL_MULTIPLIER, self.MAX_POLL_INTERVAL)

    def _fetch_result(self, result_url: str) -> list[dict[str, Any]]:
        # ``result_url`` comes from the remote job-status response, not from
        # operator input, so it is validated for SSRF before being fetched: a
        # compromised/rogue endpoint could otherwise point it at internal or
        # cloud-metadata addresses and have the worker fetch them server-side.
        # ``validate_and_resolve_url`` is a no-op (returns no pinned IPs) when
        # SSRF protection is disabled -- the default -- so behavior is unchanged
        # unless an operator opts in; when enabled it blocks internal targets
        # and pins DNS to the validated IPs.  This mirrors the shared pattern in
        # ``lfx.components.data_source.api_request``.
        _validated_url, validated_ips = validate_and_resolve_url(result_url)
        with self._build_client(result_url, validated_ips) as client:
            response = client.get(result_url)
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            return []

        try:
            payload = response.json()
        except ValueError:
            return [json.loads(line) for line in text.splitlines() if line.strip()]

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        return []

    def _build_client(self, url: str, validated_ips: list[str]) -> httpx.Client:
        """Create the HTTP client for ``url``, pinning DNS when SSRF protection applies.

        Used for the submit, poll, and result-fetch requests.  Returns a client
        that pins DNS to ``validated_ips`` (preventing rebinding) when SSRF
        protection is enabled and the host resolved to validated IPs; otherwise a
        standard client (protection disabled, allowlisted host, or hostname
        extraction failure).
        """
        if is_ssrf_protection_enabled() and validated_ips:
            hostname = httpx.URL(url).host
            if hostname:
                return create_ssrf_protected_sync_client(
                    hostname=hostname, validated_ips=validated_ips, timeout=self.REQUEST_TIMEOUT
                )
        return httpx.Client(timeout=self.REQUEST_TIMEOUT)

    def _build_ocr_options(self) -> dict[str, Any]:
        return self._collect_options(
            [
                "use_doc_orientation_classify",
                "use_doc_unwarping",
                "use_textline_orientation",
                "text_det_thresh",
                "text_det_box_thresh",
                "text_det_unclip_ratio",
                "text_rec_score_thresh",
            ]
        )

    def _build_document_parsing_options(self) -> dict[str, Any]:
        return self._collect_options(
            [
                "use_doc_orientation_classify",
                "use_doc_unwarping",
                "use_table_recognition",
                "use_formula_recognition",
                "use_chart_recognition",
                "use_seal_recognition",
                "prettify_markdown",
                "temperature",
                "top_p",
                "visualize",
            ]
        )

    def _collect_options(self, option_names: list[str]) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for name in option_names:
            value = getattr(self, name, None)
            if value is not None:
                options[name] = value
        return options

    def _ocr_result_to_data(self, job_id: str, jsonl_data: list[dict[str, Any]], file_path: Path) -> Data:
        pages_payload: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for line_obj in jsonl_data:
            result = line_obj.get("result", line_obj)
            for item in result.get("ocrResults", []) or []:
                pruned_result = item.get("prunedResult", {}) or {}
                rec_texts = pruned_result.get("rec_texts", []) or []
                if rec_texts:
                    text_parts.append("\n".join(str(text) for text in rec_texts))
                pages_payload.append(
                    {
                        "pruned_result": pruned_result,
                        "ocr_image_url": item.get("ocrImage"),
                    }
                )

        text = "\n\n".join(part for part in text_parts if part)
        return Data(
            text=text,
            data={
                self.SERVER_FILE_PATH_FIELDNAME: str(file_path),
                "text": text,
                "task_type": "ocr",
                "output_format": "plain_text",
                "model": self.model,
                "job_id": job_id,
                "pages": pages_payload,
            },
        )

    def _document_result_to_data(self, job_id: str, jsonl_data: list[dict[str, Any]], file_path: Path) -> Data:
        pages_payload: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for line_obj in jsonl_data:
            result = line_obj.get("result", line_obj)
            layout_results = result.get("layoutParsingResults", []) or []
            if layout_results:
                self._append_layout_results(layout_results, pages_payload, text_parts)
                continue
            self._append_ocr_fallback_results(result.get("ocrResults", []) or [], pages_payload, text_parts)

        markdown_text = "\n\n".join(part for part in text_parts if part)
        return Data(
            text=markdown_text,
            data={
                self.SERVER_FILE_PATH_FIELDNAME: str(file_path),
                "text": markdown_text,
                "task_type": "document_parsing",
                "output_format": "markdown",
                "model": self.model,
                "job_id": job_id,
                "pages": pages_payload,
            },
        )

    def _append_layout_results(
        self,
        layout_results: list[dict[str, Any]],
        pages_payload: list[dict[str, Any]],
        text_parts: list[str],
    ) -> None:
        for item in layout_results:
            markdown = item.get("markdown", {}) or {}
            markdown_text = markdown.get("text") or item.get("markdown_text") or ""
            if markdown_text:
                text_parts.append(str(markdown_text))
            pages_payload.append(
                {
                    "markdown_text": markdown_text,
                    "markdown_images": markdown.get("images", {}) or {},
                    "output_images": item.get("outputImages", {}) or {},
                }
            )

    def _append_ocr_fallback_results(
        self,
        ocr_results: list[dict[str, Any]],
        pages_payload: list[dict[str, Any]],
        text_parts: list[str],
    ) -> None:
        for item in ocr_results:
            pruned_result = item.get("prunedResult", {}) or {}
            rec_texts = pruned_result.get("rec_texts", []) or []
            text = "\n".join(str(text) for text in rec_texts)
            if text:
                text_parts.append(text)
            pages_payload.append(
                {
                    "markdown_text": text,
                    "markdown_images": {},
                    "output_images": {},
                    "pruned_result": pruned_result,
                    "ocr_image_url": item.get("ocrImage"),
                }
            )

    def _format_paddleocr_error(self, error: Exception) -> str:
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code in {401, 403}:
                return "PaddleOCR authentication failed. Please check the AI Studio Access Token."
            return f"PaddleOCR API error ({status_code}): {error.response.text}"
        if isinstance(error, httpx.TimeoutException | TimeoutError):
            return "PaddleOCR job timed out. Increase the timeout or try again later."
        if isinstance(error, httpx.HTTPError):
            return f"PaddleOCR network error: {error}"
        return f"PaddleOCR failed: {error}"
