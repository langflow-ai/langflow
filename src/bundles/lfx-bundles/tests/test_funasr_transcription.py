from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from lfx_bundles.funasr import FunASRTranscriptionComponent

if TYPE_CHECKING:
    from collections.abc import Callable


def _component(audio_file: Path, **overrides: Any) -> FunASRTranscriptionComponent:
    component = FunASRTranscriptionComponent()
    component._attributes.update(
        {
            "audio_file": str(audio_file),
            "base_url": "http://127.0.0.1:8000/v1",
            "model": "sensevoice",
            "api_key": "",
            "language": "",
            "timeout": 120,
            **overrides,
        }
    )
    return component


def _response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    request = httpx.Request("POST", "http://127.0.0.1:8000/v1/audio/transcriptions")
    return httpx.Response(status_code, json=payload, request=request)


def _allow_path(path: str | Path, *, scope_ids: tuple[str, ...]) -> Path:
    del scope_ids
    return Path(path)


def test_component_contract() -> None:
    component = FunASRTranscriptionComponent()
    inputs = {item.name: item for item in component.inputs}
    outputs = {item.name: item for item in component.outputs}

    assert component.display_name == "FunASR Transcription"
    assert component.icon == "AudioLines"
    assert component.documentation == "https://www.funasr.com/openai-api.html"
    assert inputs["audio_file"].required is True
    assert inputs["base_url"].value == "http://127.0.0.1:8000/v1"
    assert inputs["model"].value == "sensevoice"
    assert inputs["api_key"].required is False
    assert inputs["language"].advanced is True
    assert inputs["timeout"].value == 120
    assert outputs["transcript"].method == "transcribe"


def test_transcribes_uploaded_audio_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"audio-bytes")
    observed: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        observed["url"] = url
        observed["headers"] = kwargs["headers"]
        observed["data"] = kwargs["data"]
        observed["timeout"] = kwargs["timeout"]
        filename, handle, content_type = kwargs["files"]["file"]
        observed["filename"] = filename
        observed["body"] = handle.read()
        observed["content_type"] = content_type
        return _response(200, {"text": "欢迎使用 FunASR"})

    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.enforce_local_file_access",
        _allow_path,
    )
    monkeypatch.setattr("lfx_bundles.funasr.funasr_transcription.ssrf_safe_httpx_post", fake_post)

    result = _component(audio_file).transcribe()

    assert result.text == "欢迎使用 FunASR"
    assert result.data == {
        "text": "欢迎使用 FunASR",
        "model": "sensevoice",
        "language": None,
        "endpoint": "http://127.0.0.1:8000/v1/audio/transcriptions",
    }
    assert observed == {
        "url": "http://127.0.0.1:8000/v1/audio/transcriptions",
        "headers": {"Accept": "application/json"},
        "data": {"model": "sensevoice", "response_format": "json"},
        "timeout": 120.0,
        "filename": "sample.wav",
        "body": b"audio-bytes",
        "content_type": "audio/x-wav",
    }


def test_forwards_optional_gateway_key_language_and_full_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_file = tmp_path / "sample.mp3"
    audio_file.write_bytes(b"audio")
    observed: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        observed["url"] = url
        observed["headers"] = kwargs["headers"]
        observed["data"] = kwargs["data"]
        return _response(200, {"text": "transcript"})

    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.enforce_local_file_access",
        _allow_path,
    )
    monkeypatch.setattr("lfx_bundles.funasr.funasr_transcription.ssrf_safe_httpx_post", fake_post)

    result = _component(
        audio_file,
        base_url="https://asr.example.com/v1/audio/transcriptions/",
        api_key="gateway-secret",  # pragma: allowlist secret
        language="zh",
        model="sensevoice-small",
    ).transcribe()

    assert result.text == "transcript"
    assert observed == {
        "url": "https://asr.example.com/v1/audio/transcriptions",
        "headers": {
            "Accept": "application/json",
            "Authorization": "Bearer gateway-secret",  # pragma: allowlist secret
        },
        "data": {"model": "sensevoice-small", "response_format": "json", "language": "zh"},
    }


def test_opens_the_validated_resolved_audio_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_file = tmp_path / "requested.wav"
    requested_file.write_bytes(b"untrusted-audio")
    allowed_file = tmp_path / "allowed.wav"
    allowed_file.write_bytes(b"validated-audio")
    observed_body = b""

    def allow_validated_path(_path: str | Path, *, scope_ids: tuple[str, ...]) -> Path:
        del scope_ids
        return allowed_file

    def fake_post(_url: str, **kwargs: Any) -> httpx.Response:
        nonlocal observed_body
        observed_body = kwargs["files"]["file"][1].read()
        return _response(200, {"text": "validated transcript"})

    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.enforce_local_file_access",
        allow_validated_path,
    )
    monkeypatch.setattr("lfx_bundles.funasr.funasr_transcription.ssrf_safe_httpx_post", fake_post)

    result = _component(requested_file).transcribe()

    assert result.text == "validated transcript"
    assert observed_body == b"validated-audio"


def test_rejects_untrusted_audio_before_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_file = tmp_path / "outside.wav"
    audio_file.write_bytes(b"audio")
    requested = False

    def reject_path(_path: str | Path, *, scope_ids: tuple[str, ...]) -> Path:
        del scope_ids
        msg = "outside the authenticated user's storage scope"
        raise ValueError(msg)

    def fake_post(_url: str, **_kwargs: Any) -> httpx.Response:
        nonlocal requested
        requested = True
        return _response(200, {"text": "should not happen"})

    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.enforce_local_file_access",
        reject_path,
    )
    monkeypatch.setattr("lfx_bundles.funasr.funasr_transcription.ssrf_safe_httpx_post", fake_post)

    result = _component(audio_file).transcribe()

    assert requested is False
    assert "outside the authenticated user's storage scope" in result.data["error"]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("", "FunASR Base URL is required"),
        ("ftp://example.com/v1", "must use http or https"),
        ("http://user:pass@example.com/v1", "must not contain embedded credentials"),
    ],
)
def test_rejects_invalid_base_url(
    tmp_path: Path,
    base_url: str,
    expected: str,
) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"audio")

    result = _component(audio_file, base_url=base_url).transcribe()

    assert expected in result.data["error"]


@pytest.mark.parametrize(
    ("response_factory", "expected"),
    [
        (lambda: _response(503, {"detail": "model unavailable"}), "503"),
        (lambda: _response(200, {"unexpected": "shape"}), "missing a text transcript"),
    ],
)
def test_surfaces_provider_response_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response_factory: Callable[[], httpx.Response],
    expected: str,
) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"audio")
    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.enforce_local_file_access",
        _allow_path,
    )
    monkeypatch.setattr(
        "lfx_bundles.funasr.funasr_transcription.ssrf_safe_httpx_post",
        lambda _url, **_kwargs: response_factory(),
    )

    result = _component(audio_file).transcribe()

    assert expected in result.data["error"]
