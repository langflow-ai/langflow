"""Contract tests for the Lokutor text-to-speech and speech-to-text components."""

from __future__ import annotations

import base64
import io
import json
import wave
from pathlib import Path

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")

from lfx_bundles.lokutor import LokutorSpeechToTextComponent, LokutorTextToSpeechComponent
from lfx_bundles.lokutor import lokutor_speech_to_text as stt_module

API_KEY = "test-lokutor-key"  # pragma: allowlist secret
TTS_URL = "https://api.lokutor.com/v1/tts/synthesize"
STT_URL = "https://api.lokutor.com/v1/speech-to-text"


def _wav(seconds: float = 0.1, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def _tts(**overrides) -> LokutorTextToSpeechComponent:
    values = {"api_key": API_KEY, "text": "Hello", "voice": "F1", "language": "en", "timeout": 30}
    return LokutorTextToSpeechComponent(**{**values, **overrides})


def _stt(**overrides) -> LokutorSpeechToTextComponent:
    values = {"api_key": API_KEY, "language": "auto", "timeout": 30}
    return LokutorSpeechToTextComponent(**{**values, **overrides})


def test_component_contract() -> None:
    tts, stt = LokutorTextToSpeechComponent(), LokutorSpeechToTextComponent()
    assert {i.name for i in tts.inputs} >= {"api_key", "text", "voice", "language", "base_url"}
    assert {o.name for o in tts.outputs} == {"audio"}
    assert {i.name for i in stt.inputs} >= {"api_key", "audio_file", "audio_data", "language", "diarize"}
    assert {o.name for o in stt.outputs} == {"transcript", "details"}
    assert tts.display_name == "Lokutor Text to Speech"
    assert stt.display_name == "Lokutor Speech to Text"


@respx.mock
async def test_tts_posts_expected_payload_and_returns_audio() -> None:
    audio = _wav(0.5, 16000)
    route = respx.post(TTS_URL).mock(
        return_value=httpx.Response(200, content=audio, headers={"content-type": "audio/wav"})
    )

    result = await _tts(voice="M2", language="es", text="Hola", temperature=0.5).synthesize()

    request = route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert json.loads(request.content) == {"text": "Hola", "voice": "M2", "language": "es", "temperature": 0.5}
    assert base64.b64decode(result.data["audio_base64"]) == audio
    assert result.data["mime_type"] == "audio/wav"
    assert result.data["sample_rate"] == 16000
    assert result.data["duration_seconds"] == 0.5
    assert result.data["characters"] == 4
    assert result.text == "Hola"


@respx.mock
async def test_tts_auto_language_sends_no_language() -> None:
    route = respx.post(TTS_URL).mock(return_value=httpx.Response(200, content=_wav()))

    await _tts(language="auto").synthesize()

    assert "language" not in json.loads(route.calls[0].request.content)


@respx.mock
async def test_tts_error_is_raised_without_leaking_the_key() -> None:
    respx.post(TTS_URL).mock(
        return_value=httpx.Response(
            402, json={"detail": {"status": "quota_exceeded", "message": "Top up your balance."}}
        )
    )

    with pytest.raises(ValueError, match=r"HTTP 402: quota_exceeded: Top up your balance\.") as info:
        await _tts().synthesize()

    assert API_KEY not in str(info.value)


@respx.mock
async def test_tts_redirect_is_an_error_not_audio() -> None:
    respx.post(TTS_URL).mock(return_value=httpx.Response(307, content=b"moved"))

    with pytest.raises(ValueError, match="HTTP 307"):
        await _tts().synthesize()


async def test_tts_requires_key_and_text() -> None:
    with pytest.raises(ValueError, match="API Key is required"):
        await _tts(api_key="").synthesize()
    with pytest.raises(ValueError, match="Text is required"):
        await _tts(text="  ").synthesize()
    with pytest.raises(ValueError, match="longer than"):
        await _tts(text="a" * 10_001).synthesize()


async def test_base_url_must_not_embed_credentials() -> None:
    with pytest.raises(ValueError, match="embedded credentials"):
        await _tts(base_url="https://user:pass@api.lokutor.com/v1").synthesize()


@respx.mock
async def test_stt_transcribes_audio_data_from_text_to_speech() -> None:
    from lfx.schema.data import Data

    route = respx.post(STT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "language_code": "eng",
                "language_probability": 1.0,
                "text": " Hello. ",
                "words": [
                    {"text": "hello", "start": 0.1, "end": 0.4, "type": "word", "speaker_id": "speaker_0"},
                    {"text": " ", "start": 0.4, "end": 0.5, "type": "spacing", "speaker_id": "speaker_0"},
                ],
            },
        )
    )
    audio = Data(data={"audio_base64": base64.b64encode(_wav()).decode()})
    component = _stt(audio_data=audio, language="en", diarize=True, num_speakers=2)

    message = await component.transcribe_message()
    details = await component.transcribe_details()

    assert message.text == "Hello."
    assert details.data["language_code"] == "eng"
    assert [w["text"] for w in details.data["words"]] == ["hello"]
    assert route.call_count == 1  # both outputs share one billed request
    request = route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    body = request.content
    for field, value in (("language_code", "en"), ("diarize", "true"), ("num_speakers", "2")):
        assert f'name="{field}"'.encode() in body
        assert value.encode() in body
    assert b'name="file"' in body


@respx.mock
async def test_stt_reads_uploaded_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "call.wav"
    path.write_bytes(_wav())
    respx.post(STT_URL).mock(return_value=httpx.Response(200, json={"text": "ok", "words": []}))
    monkeypatch.setattr("lfx_bundles.lokutor.lokutor_common.enforce_local_file_access", lambda p, **_: Path(p))

    message = await _stt(audio_file=str(path)).transcribe_message()

    assert message.text == "ok"


@respx.mock
async def test_stt_error_and_missing_audio() -> None:
    respx.post(STT_URL).mock(
        return_value=httpx.Response(400, json={"detail": {"status": "unsupported_audio", "message": "Not a WAV."}})
    )
    from lfx.schema.data import Data

    audio = Data(data={"audio_base64": base64.b64encode(b"not wav").decode()})
    with pytest.raises(ValueError, match="unsupported_audio: Not a WAV"):
        await _stt(audio_data=audio).transcribe_message()
    with pytest.raises(ValueError, match="Provide an Audio File"):
        await _stt().transcribe_message()
    with pytest.raises(ValueError, match="between 1 and 32"):
        await _stt(audio_data=audio, diarize=True, num_speakers=99).transcribe_message()


@respx.mock
async def test_stt_redirect_is_an_error_not_a_transcript() -> None:
    respx.post(STT_URL).mock(return_value=httpx.Response(307, json={"text": "not a transcript"}))
    from lfx.schema.data import Data

    audio = Data(data={"audio_base64": base64.b64encode(_wav()).decode()})
    with pytest.raises(ValueError, match="HTTP 307"):
        await _stt(audio_data=audio).transcribe_message()


def test_modules_use_the_ssrf_guard() -> None:
    assert hasattr(stt_module, "ssrf_safe_strict_httpx_post")
