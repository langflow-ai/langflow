"""Unit tests for the MiniCPM-OCR extension bundle (``lfx-minicpm``).

The component calls an OpenAI-compatible endpoint with ``httpx``; the tests
replace the SSRF resolver and the HTTP client so no network access is required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import httpx
import pytest
from lfx.base.data.base_file import BaseFileComponent
from lfx.schema.data import Data
from lfx_minicpm import MiniCPMOCRComponent

if TYPE_CHECKING:
    from pathlib import Path

MODULE = "lfx_minicpm.components.minicpm.minicpm_ocr"
ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"


class FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> httpx.Response:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.responses.pop(0)


def _response(status: int = 200, payload: object | None = None, text: str = "") -> httpx.Response:
    request = httpx.Request("POST", ENDPOINT)
    if payload is not None:
        return httpx.Response(status, json=payload, request=request)
    return httpx.Response(status, text=text, request=request)


def _completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _write_minimal_pdf(path: Path) -> None:
    """Write a one-page PDF without external dependencies."""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n<</Size 4/Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    path.write_bytes(out)


@pytest.fixture
def component(monkeypatch: pytest.MonkeyPatch) -> MiniCPMOCRComponent:
    monkeypatch.setattr(f"{MODULE}.validate_and_resolve_connector_url", lambda url: (url, []))
    instance = MiniCPMOCRComponent()
    instance.base_url = "http://127.0.0.1:8000"
    instance.model = "minicpm-ocr"
    instance.api_key = ""
    instance.prompt = "Text Recognition:"
    instance.timeout = 30
    return instance


def _install_client(monkeypatch: pytest.MonkeyPatch, responses: list[httpx.Response]) -> FakeClient:
    client = FakeClient(responses)
    monkeypatch.setattr(MiniCPMOCRComponent, "_build_client", lambda *_args: client)
    return client


def _file(tmp_path: Path, name: str = "page.png", content: bytes = b"png-bytes") -> BaseFileComponent.BaseFile:
    path = tmp_path / name
    path.write_bytes(content)
    return BaseFileComponent.BaseFile(Data(data={"file_path": str(path)}), path)


def test_recognizes_image_and_sends_image_before_prompt(
    component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _install_client(monkeypatch, [_response(payload=_completion("  Hello  "))])
    file = _file(tmp_path)

    component.process_files([file])

    assert file.data[0].text == "Hello"
    assert client.calls[0]["url"] == ENDPOINT
    assert client.calls[0]["headers"] == {"Content-Type": "application/json"}
    content = client.calls[0]["json"]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["image_url", "text"]
    assert content[1]["text"] == "Text Recognition:"
    assert client.calls[0]["json"]["mm_processor_kwargs"] == {"max_slice_nums": 9, "downsample_mode": "4x"}


def test_sends_bearer_key_and_normalizes_v1(
    component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    component.base_url = "http://127.0.0.1:8000/v1/"
    component.api_key = "secret"  # pragma: allowlist secret
    client = _install_client(monkeypatch, [_response(payload=_completion("ok"))])

    component.process_files([_file(tmp_path)])

    assert client.calls[0]["url"] == ENDPOINT
    assert client.calls[0]["headers"]["Authorization"] == "Bearer secret"


def test_retries_without_slice_arguments_when_endpoint_rejects_them(
    component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _install_client(
        monkeypatch,
        [
            _response(400, text="bad request"),
            _response(payload=_completion("retried")),
        ],
    )
    file = _file(tmp_path)

    component.process_files([file])

    assert len(client.calls) == 2
    assert "mm_processor_kwargs" not in client.calls[1]["json"]


def test_rejects_invalid_timeouts(component: MiniCPMOCRComponent, tmp_path: Path) -> None:
    file = _file(tmp_path)
    component.timeout = "abc"
    with pytest.raises(ValueError, match="Timeout must be a number"):
        component.process_files([file])

    component.timeout = -5
    with pytest.raises(ValueError, match="Timeout must be greater than zero"):
        component.process_files([file])


def test_reports_http_error(component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_client(monkeypatch, [_response(503, text="model not loaded")])

    with pytest.raises(RuntimeError, match="HTTP 503"):
        component.process_files([_file(tmp_path)])


def test_reports_invalid_response(
    component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_client(monkeypatch, [_response(text="<html>gateway</html>")])

    with pytest.raises(RuntimeError, match="invalid response"):
        component.process_files([_file(tmp_path)])


def test_reports_empty_result(component: MiniCPMOCRComponent, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_client(monkeypatch, [_response(payload=_completion("   "))])

    with pytest.raises(RuntimeError, match="empty result"):
        component.process_files([_file(tmp_path)])


def test_recognizes_every_pdf_page(
    component: MiniCPMOCRComponent,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        MiniCPMOCRComponent,
        "_render_pdf",
        lambda _self, _path: iter([(b"page-1", "image/png"), (b"page-2", "image/png")]),
    )
    client = _install_client(monkeypatch, [_response(payload=_completion("A")), _response(payload=_completion("B"))])
    file = _file(tmp_path, name="scan.pdf", content=b"%PDF-1.4")

    component.process_files([file])

    assert len(client.calls) == 2
    assert file.data[0].data["page_count"] == 2
    assert file.data[0].text == "A\n\nB"


def test_renders_pdf_pages_locally(component: MiniCPMOCRComponent, tmp_path: Path) -> None:
    path = tmp_path / "mini.pdf"
    _write_minimal_pdf(path)

    pages = list(component._render_pdf(path))

    assert len(pages) == 1
    assert pages[0][1] == "image/png"
    assert pages[0][0].startswith(b"\x89PNG")
