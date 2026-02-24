"""Tests for CAMB AI Langflow components.

Unit tests use mocks; integration tests (marked @pytest.mark.integration) call
the real CAMB API and require CAMB_API_KEY + CAMB_AUDIO_SAMPLE in .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest
from dotenv import load_dotenv

# Load .env from src/lfx root
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

from lfx.components.camb._helpers import (
    add_wav_header,
    detect_audio_format,
    poll_task,
    save_audio,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("CAMB_API_KEY", "")
AUDIO_SAMPLE = os.environ.get("CAMB_AUDIO_SAMPLE", "")

needs_api = pytest.mark.skipif(not API_KEY, reason="CAMB_API_KEY not set")
needs_audio = pytest.mark.skipif(
    not AUDIO_SAMPLE or not Path(AUDIO_SAMPLE).exists(),
    reason="CAMB_AUDIO_SAMPLE not set or file missing",
)


# ---------------------------------------------------------------------------
# Module / Lazy-loading tests
# ---------------------------------------------------------------------------


class TestModuleRegistration:
    """Verify CAMB module is properly registered and lazily loaded."""

    def test_camb_in_parent_all(self):
        from lfx.components import __all__ as parent_all

        assert "camb" in parent_all

    def test_camb_in_parent_dynamic_imports(self):
        from lfx.components import _dynamic_imports

        assert "camb" in _dynamic_imports
        assert _dynamic_imports["camb"] == "__module__"

    def test_import_camb_module(self):
        from lfx.components import camb

        assert hasattr(camb, "_dynamic_imports")
        assert hasattr(camb, "__all__")

    def test_camb_dir_lists_all_components(self):
        from lfx.components import camb

        names = dir(camb)
        expected = [
            "CambAudioSeparationComponent",
            "CambTextToSoundComponent",
            "CambTranscribeComponent",
            "CambTranslateComponent",
            "CambTranslatedTTSComponent",
            "CambTTSComponent",
            "CambVoiceCloneComponent",
            "CambVoiceListComponent",
        ]
        for name in expected:
            assert name in names

    def test_lazy_import_individual_component(self):
        from lfx.components.camb import CambTTSComponent

        assert CambTTSComponent.display_name == "CAMB AI Text-to-Speech"

    def test_component_discovery_from_parent(self):
        from lfx.components import _discover_components_from_module, _dynamic_imports

        _discover_components_from_module("camb")
        camb_entries = [k for k, v in _dynamic_imports.items() if isinstance(v, str) and v.startswith("camb.")]
        assert len(camb_entries) == 8

    def test_direct_import_from_parent(self):
        from lfx.components import CambTranslateComponent

        assert CambTranslateComponent.display_name == "CAMB AI Translate"

    def test_invalid_attr_raises(self):
        from lfx.components import camb

        with pytest.raises(AttributeError):
            _ = camb.NonExistentComponent


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestDetectAudioFormat:
    def test_wav(self):
        assert detect_audio_format(b"RIFF" + b"\x00" * 100) == "wav"

    def test_mp3_id3(self):
        assert detect_audio_format(b"ID3" + b"\x00" * 100) == "mp3"

    def test_mp3_sync(self):
        assert detect_audio_format(b"\xff\xfb" + b"\x00" * 100) == "mp3"

    def test_flac(self):
        assert detect_audio_format(b"fLaC" + b"\x00" * 100) == "flac"

    def test_ogg(self):
        assert detect_audio_format(b"OggS" + b"\x00" * 100) == "ogg"

    def test_unknown_defaults_to_wav(self):
        assert detect_audio_format(b"\x00" * 100) == "wav"

    def test_empty_data(self):
        assert detect_audio_format(b"") == "wav"


class TestAddWavHeader:
    def test_header_format(self):
        pcm = b"\x00" * 100
        wav = add_wav_header(pcm)
        assert wav.startswith(b"RIFF")
        assert b"WAVE" in wav[:12]
        assert wav.endswith(pcm)

    def test_header_length(self):
        pcm = b"\x01\x02" * 50
        wav = add_wav_header(pcm)
        assert len(wav) == 44 + len(pcm)


class TestSaveAudio:
    def test_saves_file(self):
        data = b"test audio data"
        path = save_audio(data, "wav")
        assert path.endswith(".wav")
        assert Path(path).read_bytes() == data
        Path(path).unlink()

    def test_custom_extension(self):
        path = save_audio(b"data", "mp3")
        assert path.endswith(".mp3")
        Path(path).unlink()


class TestPollTask:
    @pytest.mark.asyncio
    async def test_poll_completed(self):
        client = MagicMock()
        status = Mock(status="completed", run_id="run-1")
        get_fn = AsyncMock(return_value=status)
        result = await poll_task(client, get_fn, "task-1", max_attempts=3, interval=0.01)
        assert result.run_id == "run-1"

    @pytest.mark.asyncio
    async def test_poll_failed(self):
        client = MagicMock()
        status = Mock(status="failed", exception_reason="quota exceeded")
        get_fn = AsyncMock(return_value=status)
        with pytest.raises(RuntimeError, match="CAMB.AI task failed"):
            await poll_task(client, get_fn, "task-1", max_attempts=3, interval=0.01)

    @pytest.mark.asyncio
    async def test_poll_timeout(self):
        client = MagicMock()
        status = Mock(status="processing")
        get_fn = AsyncMock(return_value=status)
        with pytest.raises(TimeoutError, match="did not complete"):
            await poll_task(client, get_fn, "task-1", max_attempts=2, interval=0.01)


# ---------------------------------------------------------------------------
# Component display metadata
# ---------------------------------------------------------------------------


class TestComponentMetadata:
    """Verify display_name, icon, and name for every component."""

    EXPECTED = [
        ("CambTTSComponent", "CAMB AI Text-to-Speech", "CambTTS"),
        ("CambTranslateComponent", "CAMB AI Translate", "CambTranslate"),
        ("CambTranscribeComponent", "CAMB AI Transcribe", "CambTranscribe"),
        ("CambTranslatedTTSComponent", "CAMB AI Translated TTS", "CambTranslatedTTS"),
        ("CambVoiceCloneComponent", "CAMB AI Voice Clone", "CambVoiceClone"),
        ("CambVoiceListComponent", "CAMB AI Voice List", "CambVoiceList"),
        ("CambTextToSoundComponent", "CAMB AI Text-to-Sound", "CambTextToSound"),
        ("CambAudioSeparationComponent", "CAMB AI Audio Separation", "CambAudioSeparation"),
    ]

    @pytest.mark.parametrize("cls_name,display,name", EXPECTED)
    def test_metadata(self, cls_name, display, name):
        import lfx.components.camb as camb_mod

        cls = getattr(camb_mod, cls_name)
        assert cls.display_name == display
        assert cls.name == name
        assert cls.icon == "camb-ai"


# ---------------------------------------------------------------------------
# Unit tests (mocked SDK)
# ---------------------------------------------------------------------------


class TestTTSComponent:
    @patch("camb.StreamTtsOutputConfiguration", create=True)
    @patch("lfx.components.camb.camb_tts.get_async_client")
    def test_tts_returns_file_path(self, mock_get_client, mock_config):
        from lfx.components.camb import CambTTSComponent

        mock_client = MagicMock()

        async def fake_tts(**kwargs):
            for chunk in [b"RIFF", b"\x00" * 40, b"audio"]:
                yield chunk

        mock_client.text_to_speech.tts = fake_tts
        mock_get_client.return_value = mock_client

        comp = CambTTSComponent()
        comp.api_key = "test-key"
        comp.text = "Hello world"
        comp.language = "en-us"
        comp.voice_id = 147320
        comp.speech_model = "mars-flash"
        comp.user_instructions = ""

        result = comp.generate_speech()
        assert result.data["file_path"].endswith(".wav")
        Path(result.data["file_path"]).unlink(missing_ok=True)

    @patch("camb.StreamTtsOutputConfiguration", create=True)
    @patch("lfx.components.camb.camb_tts.get_async_client")
    def test_tts_empty_audio_returns_error(self, mock_get_client, mock_config):
        from lfx.components.camb import CambTTSComponent

        mock_client = MagicMock()

        async def fake_tts(**kwargs):
            return
            yield  # noqa: RET504 – make it an async generator

        mock_client.text_to_speech.tts = fake_tts
        mock_get_client.return_value = mock_client

        comp = CambTTSComponent()
        comp.api_key = "test-key"
        comp.text = "Hello"
        comp.language = "en-us"
        comp.voice_id = 147320
        comp.speech_model = "mars-flash"
        comp.user_instructions = ""

        result = comp.generate_speech()
        assert "error" in result.data


class TestTranslateComponent:
    @patch("lfx.components.camb.camb_translate.get_async_client")
    def test_translate_success(self, mock_get_client):
        from lfx.components.camb import CambTranslateComponent

        mock_client = MagicMock()
        mock_result = Mock()
        mock_result.__str__ = lambda self: "Hola mundo"
        mock_client.translation.translation_stream = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_client

        comp = CambTranslateComponent()
        comp.api_key = "test-key"
        comp.text = "Hello world"
        comp.source_language = 1
        comp.target_language = 2
        comp.formality = 0

        result = comp.translate_text()
        assert result.data["translated_text"] == "Hola mundo"

    @patch("lfx.components.camb.camb_translate.get_async_client")
    def test_translate_none_result(self, mock_get_client):
        from lfx.components.camb import CambTranslateComponent

        mock_client = MagicMock()
        mock_client.translation.translation_stream = AsyncMock(return_value=None)
        mock_get_client.return_value = mock_client

        comp = CambTranslateComponent()
        comp.api_key = "test-key"
        comp.text = "Hello world"
        comp.source_language = 1
        comp.target_language = 2
        comp.formality = 0

        result = comp.translate_text()
        assert "error" in result.data

    @patch("lfx.components.camb.camb_translate.get_async_client")
    def test_translate_api_error_workaround(self, mock_get_client):
        from camb.core.api_error import ApiError

        from lfx.components.camb import CambTranslateComponent

        mock_client = MagicMock()
        mock_client.translation.translation_stream = AsyncMock(
            side_effect=ApiError(status_code=200, body="Hola mundo")
        )
        mock_get_client.return_value = mock_client

        comp = CambTranslateComponent()
        comp.api_key = "test-key"
        comp.text = "Hello world"
        comp.source_language = 1
        comp.target_language = 2
        comp.formality = 0

        result = comp.translate_text()
        assert result.data["translated_text"] == "Hola mundo"


class TestTranscribeComponent:
    @patch("lfx.components.camb.camb_transcribe.poll_task")
    @patch("lfx.components.camb.camb_transcribe.get_async_client")
    def test_transcribe_with_url(self, mock_get_client, mock_poll):
        from lfx.components.camb import CambTranscribeComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_create = Mock(task_id="task-1")
        mock_client.transcription.create_transcription = AsyncMock(return_value=mock_create)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        mock_seg = Mock(start=0.0, end=1.5, text="Hello world", speaker="A")
        mock_transcription = Mock(transcript=[mock_seg])
        mock_client.transcription.get_transcription_result = AsyncMock(return_value=mock_transcription)

        comp = CambTranscribeComponent()
        comp.api_key = "test-key"
        comp.language = 1
        comp.audio_file = ""
        comp.audio_url = "https://example.com/audio.mp3"

        result = comp.transcribe_audio()
        assert result.data["text"] == "Hello world"
        assert len(result.data["segments"]) == 1

    def test_transcribe_no_source_returns_error(self):
        from lfx.components.camb import CambTranscribeComponent

        comp = CambTranscribeComponent()
        comp.api_key = "test-key"
        comp.language = 1
        comp.audio_file = ""
        comp.audio_url = ""

        result = comp.transcribe_audio()
        assert "error" in result.data


class TestTranslatedTTSComponent:
    @patch("httpx.AsyncClient")
    @patch("lfx.components.camb.camb_translated_tts.poll_task")
    @patch("lfx.components.camb.camb_translated_tts.get_async_client")
    def test_translated_tts_success(self, mock_get_client, mock_poll, mock_async_client):
        from lfx.components.camb import CambTranslatedTTSComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = Mock(task_id="task-1")
        mock_client.translated_tts.create_translated_tts = AsyncMock(return_value=mock_result)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        mock_resp = Mock(status_code=200, content=b"RIFF" + b"\x00" * 100)
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_async_client.return_value = mock_http

        comp = CambTranslatedTTSComponent()
        comp.api_key = "test-key"
        comp.text = "Hello"
        comp.source_language = 1
        comp.target_language = 2
        comp.voice_id = 147320
        comp.formality = 0

        result = comp.translated_tts()
        assert result.data["file_path"].endswith(".wav")
        Path(result.data["file_path"]).unlink(missing_ok=True)

    @patch("lfx.components.camb.camb_translated_tts.poll_task")
    @patch("lfx.components.camb.camb_translated_tts.get_async_client")
    def test_translated_tts_no_run_id(self, mock_get_client, mock_poll):
        from lfx.components.camb import CambTranslatedTTSComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = Mock(task_id="task-1")
        mock_client.translated_tts.create_translated_tts = AsyncMock(return_value=mock_result)

        mock_status = Mock(spec=[])  # no run_id attribute
        mock_poll.return_value = mock_status

        comp = CambTranslatedTTSComponent()
        comp.api_key = "test-key"
        comp.text = "Hello"
        comp.source_language = 1
        comp.target_language = 2
        comp.voice_id = 147320
        comp.formality = 0

        result = comp.translated_tts()
        assert "error" in result.data

    @patch("httpx.AsyncClient")
    @patch("lfx.components.camb.camb_translated_tts.poll_task")
    @patch("lfx.components.camb.camb_translated_tts.get_async_client")
    def test_translated_tts_http_error(self, mock_get_client, mock_poll, mock_async_client):
        from lfx.components.camb import CambTranslatedTTSComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = Mock(task_id="task-1")
        mock_client.translated_tts.create_translated_tts = AsyncMock(return_value=mock_result)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        mock_resp = Mock(status_code=500, content=b"")
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_async_client.return_value = mock_http

        comp = CambTranslatedTTSComponent()
        comp.api_key = "test-key"
        comp.text = "Hello"
        comp.source_language = 1
        comp.target_language = 2
        comp.voice_id = 147320
        comp.formality = 0

        result = comp.translated_tts()
        assert "error" in result.data
        assert "500" in result.data["error"]


class TestVoiceListComponent:
    @patch("lfx.components.camb.camb_voice_list.get_async_client")
    def test_list_voices(self, mock_get_client):
        from lfx.components.camb import CambVoiceListComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_voice = Mock(id=123, voice_name="Test Voice")
        mock_client.voice_cloning.list_voices = AsyncMock(return_value=[mock_voice])

        comp = CambVoiceListComponent()
        comp.api_key = "test-key"

        result = comp.list_voices()
        assert result.data["count"] == 1
        assert result.data["voices"][0]["id"] == 123

    @patch("lfx.components.camb.camb_voice_list.get_async_client")
    def test_list_voices_empty(self, mock_get_client):
        from lfx.components.camb import CambVoiceListComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.voice_cloning.list_voices = AsyncMock(return_value=[])

        comp = CambVoiceListComponent()
        comp.api_key = "test-key"

        result = comp.list_voices()
        assert result.data["count"] == 0
        assert result.data["voices"] == []


class TestVoiceCloneComponent:
    @patch("lfx.components.camb.camb_voice_clone.get_async_client")
    def test_clone_voice(self, mock_get_client):
        from lfx.components.camb import CambVoiceCloneComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = Mock(voice_id=999)
        mock_client.voice_cloning.create_custom_voice = AsyncMock(return_value=mock_result)

        comp = CambVoiceCloneComponent()
        comp.api_key = "test-key"
        comp.voice_name = "Test Voice"
        comp.audio_file = "/fake/path.wav"
        comp.gender = "Female"
        comp.description = ""
        comp.age = 0
        comp.language = 0

        with patch("builtins.open", mock_open(read_data=b"audio_data")):
            result = comp.clone_voice()

        assert result.data["voice_id"] == 999
        assert result.data["status"] == "created"


    @patch("lfx.components.camb.camb_voice_clone.get_async_client")
    def test_clone_voice_missing_id(self, mock_get_client):
        from lfx.components.camb import CambVoiceCloneComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = Mock(spec=[])  # no voice_id or id attribute
        mock_client.voice_cloning.create_custom_voice = AsyncMock(return_value=mock_result)

        comp = CambVoiceCloneComponent()
        comp.api_key = "test-key"
        comp.voice_name = "Test Voice"
        comp.audio_file = "/fake/path.wav"
        comp.gender = "Female"
        comp.description = ""
        comp.age = 0
        comp.language = 0

        with patch("builtins.open", mock_open(read_data=b"audio_data")):
            result = comp.clone_voice()

        assert "error" in result.data


class TestTextToSoundComponent:
    @patch("lfx.components.camb.camb_text_to_sound.poll_task")
    @patch("lfx.components.camb.camb_text_to_sound.get_async_client")
    def test_text_to_sound(self, mock_get_client, mock_poll):
        from lfx.components.camb import CambTextToSoundComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_task = Mock(task_id="task-1")
        mock_client.text_to_audio.create_text_to_audio = AsyncMock(return_value=mock_task)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        async def fake_result(run_id):
            for chunk in [b"RIFF", b"\x00" * 40, b"audio"]:
                yield chunk

        mock_client.text_to_audio.get_text_to_audio_result = fake_result

        comp = CambTextToSoundComponent()
        comp.api_key = "test-key"
        comp.prompt = "gentle rain"
        comp.duration = 0
        comp.audio_type = ""

        result = comp.generate_sound()
        assert result.data["file_path"].endswith(".wav")
        Path(result.data["file_path"]).unlink(missing_ok=True)

    @patch("lfx.components.camb.camb_text_to_sound.poll_task")
    @patch("lfx.components.camb.camb_text_to_sound.get_async_client")
    def test_text_to_sound_empty_returns_error(self, mock_get_client, mock_poll):
        from lfx.components.camb import CambTextToSoundComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_task = Mock(task_id="task-1")
        mock_client.text_to_audio.create_text_to_audio = AsyncMock(return_value=mock_task)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        async def fake_empty(run_id):
            return
            yield

        mock_client.text_to_audio.get_text_to_audio_result = fake_empty

        comp = CambTextToSoundComponent()
        comp.api_key = "test-key"
        comp.prompt = "silence"
        comp.duration = 0
        comp.audio_type = ""

        result = comp.generate_sound()
        assert "error" in result.data


class TestAudioSeparationComponent:
    @patch("lfx.components.camb.camb_audio_separation.poll_task")
    @patch("lfx.components.camb.camb_audio_separation.get_async_client")
    def test_separation_with_file(self, mock_get_client, mock_poll):
        from lfx.components.camb import CambAudioSeparationComponent

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_task = Mock(task_id="task-1")
        mock_client.audio_separation.create_audio_separation = AsyncMock(return_value=mock_task)

        mock_status = Mock(run_id="run-1")
        mock_poll.return_value = mock_status

        mock_info = Mock(
            foreground_audio_url="https://example.com/vocals.wav",
            background_audio_url="https://example.com/bg.wav",
        )
        mock_client.audio_separation.get_audio_separation_run_info = AsyncMock(return_value=mock_info)

        comp = CambAudioSeparationComponent()
        comp.api_key = "test-key"
        comp.audio_file = "/fake/audio.mp3"
        comp.audio_url = ""

        with patch("builtins.open", mock_open(read_data=b"audio")):
            result = comp.separate_audio()

        assert result.data["foreground_audio_url"] == "https://example.com/vocals.wav"
        assert result.data["background_audio_url"] == "https://example.com/bg.wav"

    def test_separation_no_source_returns_error(self):
        from lfx.components.camb import CambAudioSeparationComponent

        comp = CambAudioSeparationComponent()
        comp.api_key = "test-key"
        comp.audio_file = ""
        comp.audio_url = ""

        result = comp.separate_audio()
        assert "error" in result.data


# ---------------------------------------------------------------------------
# Integration tests (real API)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestIntegrationCambAPI:
    """Live integration tests against the real CAMB API.

    Run with:  uv run pytest tests/unit/components/camb/ -m integration -v -s
    """

    @needs_api
    def test_tts(self):
        from lfx.components.camb import CambTTSComponent

        comp = CambTTSComponent()
        comp.api_key = API_KEY
        comp.text = "Hello from CAMB AI and Langflow. This is a text to speech test."
        comp.language = "en-us"
        comp.voice_id = 147320
        comp.speech_model = "mars-flash"
        comp.user_instructions = ""

        result = comp.generate_speech()
        assert "file_path" in result.data
        path = result.data["file_path"]
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
        print(f"  TTS audio: {path}")
        Path(path).unlink(missing_ok=True)

    @needs_api
    def test_translate(self):
        from lfx.components.camb import CambTranslateComponent

        comp = CambTranslateComponent()
        comp.api_key = API_KEY
        comp.text = "Hello, how are you?"
        comp.source_language = 1
        comp.target_language = 2
        comp.formality = 0

        result = comp.translate_text()
        assert "translated_text" in result.data
        assert len(result.data["translated_text"]) > 0
        print(f"  Translation: {result.data['translated_text']}")

    @needs_api
    def test_voice_list(self):
        from lfx.components.camb import CambVoiceListComponent

        comp = CambVoiceListComponent()
        comp.api_key = API_KEY

        result = comp.list_voices()
        assert result.data["count"] > 0
        print(f"  Found {result.data['count']} voices")

    @needs_api
    @needs_audio
    def test_transcribe(self):
        from lfx.components.camb import CambTranscribeComponent

        comp = CambTranscribeComponent()
        comp.api_key = API_KEY
        comp.language = 1
        comp.audio_file = AUDIO_SAMPLE
        comp.audio_url = ""

        result = comp.transcribe_audio()
        assert "text" in result.data
        assert len(result.data["text"]) > 0
        print(f"  Transcription: {result.data['text'][:200]}")

    @needs_api
    def test_translated_tts(self):
        from lfx.components.camb import CambTranslatedTTSComponent

        comp = CambTranslatedTTSComponent()
        comp.api_key = API_KEY
        comp.text = "Hello, how are you?"
        comp.source_language = 1
        comp.target_language = 2
        comp.voice_id = 147320
        comp.formality = 0

        result = comp.translated_tts()
        assert "file_path" in result.data
        path = result.data["file_path"]
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
        print(f"  Translated TTS audio: {path}")
        Path(path).unlink(missing_ok=True)

    @needs_api
    def test_text_to_sound(self):
        from lfx.components.camb import CambTextToSoundComponent

        comp = CambTextToSoundComponent()
        comp.api_key = API_KEY
        comp.prompt = "gentle rain on a rooftop"
        comp.duration = 5.0
        comp.audio_type = "sound"

        result = comp.generate_sound()
        assert "file_path" in result.data
        path = result.data["file_path"]
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0
        print(f"  Text-to-sound audio: {path}")
        Path(path).unlink(missing_ok=True)

    @needs_api
    @needs_audio
    def test_voice_clone(self):
        from lfx.components.camb import CambVoiceCloneComponent

        comp = CambVoiceCloneComponent()
        comp.api_key = API_KEY
        comp.voice_name = "test_clone_langflow"
        comp.audio_file = AUDIO_SAMPLE
        comp.gender = "Female"
        comp.description = ""
        comp.age = 0
        comp.language = 0

        result = comp.clone_voice()
        assert "voice_id" in result.data
        assert result.data["status"] == "created"
        print(f"  Cloned voice ID: {result.data['voice_id']}")

    @needs_api
    @needs_audio
    def test_audio_separation(self):
        from lfx.components.camb import CambAudioSeparationComponent

        comp = CambAudioSeparationComponent()
        comp.api_key = API_KEY
        comp.audio_file = AUDIO_SAMPLE
        comp.audio_url = ""

        result = comp.separate_audio()
        assert "foreground_audio_url" in result.data or "background_audio_url" in result.data
        print(f"  Separation result: {result.data}")
