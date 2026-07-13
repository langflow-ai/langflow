from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from lfx.components.assemblyai import assemblyai_start_transcript
from lfx.components.assemblyai.assemblyai_start_transcript import AssemblyAITranscriptionJobCreator
from lfx.services.storage.local import LocalStorageService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any


class _Transcript:
    error = None
    id = "transcript-123"


def _component(audio_file: Path, flow_id: str, user_id: str) -> AssemblyAITranscriptionJobCreator:
    component = AssemblyAITranscriptionJobCreator()
    component._flow_id = flow_id
    component._user_id = user_id
    component._attributes.update(
        {
            "api_key": "test-key",  # pragma: allowlist secret
            "audio_file": str(audio_file),
            "audio_file_url": "",
            "speech_model": "best",
            "language_detection": False,
            "language_code": "",
            "speaker_labels": False,
            "speakers_expected": "",
            "punctuate": True,
            "format_text": True,
        }
    )
    return component


def _storage_service(root: Path) -> LocalStorageService:
    settings_service = SimpleNamespace(settings=SimpleNamespace(config_dir=str(root)))
    return LocalStorageService(session_service=None, settings_service=settings_service)


def _patch_assemblyai(
    monkeypatch: pytest.MonkeyPatch,
    submitted_audio: list[str],
) -> None:
    monkeypatch.setattr(assemblyai_start_transcript.aai, "TranscriptionConfig", lambda **_kwargs: object())

    class _Transcriber:
        def submit(self, audio: str, *, config: Any) -> _Transcript:
            del config
            submitted_audio.append(audio)
            return _Transcript()

    monkeypatch.setattr(assemblyai_start_transcript.aai, "Transcriber", _Transcriber)


@pytest.mark.parametrize(
    "untrusted_path",
    [
        lambda root, flow_id, _outside: root / flow_id / ".." / ".." / "outside" / "audio.mp3",
        lambda _root, _flow_id, outside: outside,
        lambda root, _flow_id, _outside: root / "another-flow" / "audio.mp3",
        lambda root, _flow_id, _outside: root / "another-user" / "audio.mp3",
    ],
    ids=["traversal", "absolute-outside", "other-flow", "other-user"],
)
def test_rejects_untrusted_audio_paths_before_provider_submission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    untrusted_path: Callable[[Path, str, Path], Path],
) -> None:
    flow_id = "flow-123"
    user_id = "user-456"
    storage_root = tmp_path / "storage"
    (storage_root / flow_id).mkdir(parents=True)
    outside_file = tmp_path / "outside" / "audio.mp3"
    outside_file.parent.mkdir(parents=True)
    outside_file.write_bytes(b"controlled test fixture")
    other_flow_file = storage_root / "another-flow" / "audio.mp3"
    other_flow_file.parent.mkdir(parents=True)
    other_flow_file.write_bytes(b"controlled test fixture")
    other_user_file = storage_root / "another-user" / "audio.mp3"
    other_user_file.parent.mkdir(parents=True)
    other_user_file.write_bytes(b"controlled test fixture")

    audio_file = untrusted_path(storage_root, flow_id, outside_file)
    submitted_audio: list[str] = []
    _patch_assemblyai(monkeypatch, submitted_audio)
    monkeypatch.setattr(
        assemblyai_start_transcript,
        "get_storage_service",
        lambda: _storage_service(storage_root),
        raising=False,
    )

    result = _component(audio_file, flow_id, user_id).create_transcription_job()

    assert submitted_audio == []
    assert result.data == {"error": "Error: Audio file not found"}


@pytest.mark.parametrize("namespace_id", ["flow-123", "user-456"], ids=["current-flow", "current-user"])
def test_accepts_uploaded_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, namespace_id: str) -> None:
    flow_id = "flow-123"
    user_id = "user-456"
    storage_root = tmp_path / "storage"
    audio_file = storage_root / namespace_id / "audio.mp3"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"controlled test fixture")

    submitted_audio: list[str] = []
    _patch_assemblyai(monkeypatch, submitted_audio)
    monkeypatch.setattr(
        assemblyai_start_transcript,
        "get_storage_service",
        lambda: _storage_service(storage_root),
        raising=False,
    )

    result = _component(audio_file, flow_id, user_id).create_transcription_job()

    assert submitted_audio == [str(audio_file.resolve())]
    assert result.data == {"transcript_id": "transcript-123"}
