from __future__ import annotations

import sys
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from lfx.services.storage.local import LocalStorageService

_COMPONENT_MODULE = "lfx_bundles.assemblyai.assemblyai_start_transcript"
_PARENT_MODULE = "lfx_bundles.assemblyai"
_COMPONENT_ATTRIBUTE = "assemblyai_start_transcript"
_MISSING = object()

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import Any, BinaryIO


@pytest.fixture
def assemblyai_module() -> ModuleType:
    parent_module = import_module(_PARENT_MODULE)
    previous_assemblyai = sys.modules.get("assemblyai")
    previous_component_module = sys.modules.pop(_COMPONENT_MODULE, None)
    previous_component_attribute = getattr(parent_module, _COMPONENT_ATTRIBUTE, _MISSING)
    sys.modules["assemblyai"] = MagicMock()
    try:
        yield import_module(_COMPONENT_MODULE)
    finally:
        if previous_assemblyai is None:
            sys.modules.pop("assemblyai", None)
        else:
            sys.modules["assemblyai"] = previous_assemblyai
        if previous_component_module is None:
            sys.modules.pop(_COMPONENT_MODULE, None)
        else:
            sys.modules[_COMPONENT_MODULE] = previous_component_module
        if previous_component_attribute is _MISSING:
            with suppress(AttributeError):
                delattr(parent_module, _COMPONENT_ATTRIBUTE)
        else:
            setattr(parent_module, _COMPONENT_ATTRIBUTE, previous_component_attribute)


class _Transcript:
    error = None
    id = "transcript-123"


def _component(component_class: type[Any], audio_file: Path, flow_id: str, user_id: str) -> Any:
    component = component_class()
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
    assemblyai_module: ModuleType,
    submitted_audio: list[bytes],
    submitted_handles: list[BinaryIO] | None = None,
) -> None:
    monkeypatch.setattr(assemblyai_module.aai, "TranscriptionConfig", lambda **_kwargs: object())

    class _Transcriber:
        def submit(self, audio: str | BinaryIO, *, config: Any) -> _Transcript:
            del config
            if isinstance(audio, str):
                submitted_audio.append(Path(audio).read_bytes())
            else:
                submitted_audio.append(audio.read())
                if submitted_handles is not None:
                    submitted_handles.append(audio)
            return _Transcript()

    monkeypatch.setattr(assemblyai_module.aai, "Transcriber", _Transcriber)


@pytest.mark.parametrize(
    "untrusted_path",
    [
        lambda root, flow_id, _outside: root / flow_id / ".." / ".." / "outside" / "audio.mp3",
        lambda _root, _flow_id, outside: outside,
        lambda root, _flow_id, _outside: root / "another-flow" / "audio.mp3",
        lambda root, _flow_id, _outside: root / "another-user" / "audio.mp3",
        lambda root, flow_id, _outside: root / flow_id / "missing.mp3",
    ],
    ids=["traversal", "absolute-outside", "other-flow", "other-user", "missing-current-flow"],
)
def test_rejects_untrusted_audio_paths_before_provider_submission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_module: ModuleType,
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
    submitted_audio: list[bytes] = []
    _patch_assemblyai(monkeypatch, assemblyai_module, submitted_audio)
    monkeypatch.setattr(
        assemblyai_module,
        "get_storage_service",
        lambda: _storage_service(storage_root),
        raising=False,
    )

    result = _component(
        assemblyai_module.AssemblyAITranscriptionJobCreator,
        audio_file,
        flow_id,
        user_id,
    ).create_transcription_job()

    assert submitted_audio == []
    assert result.data == {"error": "Error: Audio file not found"}


@pytest.mark.parametrize("namespace_kind", ["absolute", "traversal", "current-directory"])
def test_rejects_unsafe_namespace_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_module: ModuleType,
    namespace_kind: str,
) -> None:
    storage_root = tmp_path / "storage"
    outside_directory = tmp_path / "outside"
    if namespace_kind == "absolute":
        flow_id = str(outside_directory)
        audio_file = outside_directory / "audio.mp3"
    elif namespace_kind == "traversal":
        flow_id = "../outside"
        audio_file = outside_directory / "audio.mp3"
    else:
        flow_id = "."
        audio_file = storage_root / "audio.mp3"

    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"controlled test fixture")
    submitted_audio: list[bytes] = []
    _patch_assemblyai(monkeypatch, assemblyai_module, submitted_audio)
    monkeypatch.setattr(
        assemblyai_module,
        "get_storage_service",
        lambda: _storage_service(storage_root),
        raising=False,
    )

    result = _component(
        assemblyai_module.AssemblyAITranscriptionJobCreator,
        audio_file,
        flow_id,
        "user-456",
    ).create_transcription_job()

    assert submitted_audio == []
    assert result.data == {"error": "Error: Audio file not found"}


@pytest.mark.parametrize("namespace_id", ["flow-123", "user-456"], ids=["current-flow", "current-user"])
def test_submits_uploaded_audio_from_open_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_module: ModuleType,
    namespace_id: str,
) -> None:
    flow_id = "flow-123"
    user_id = "user-456"
    storage_root = tmp_path / "storage"
    audio_file = storage_root / namespace_id / "audio.mp3"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"controlled test fixture")

    submitted_audio: list[bytes] = []
    submitted_handles: list[BinaryIO] = []
    _patch_assemblyai(monkeypatch, assemblyai_module, submitted_audio, submitted_handles)
    monkeypatch.setattr(
        assemblyai_module,
        "get_storage_service",
        lambda: _storage_service(storage_root),
        raising=False,
    )

    result = _component(
        assemblyai_module.AssemblyAITranscriptionJobCreator,
        audio_file,
        flow_id,
        user_id,
    ).create_transcription_job()

    assert submitted_audio == [b"controlled test fixture"]
    assert len(submitted_handles) == 1
    assert submitted_handles[0].closed
    assert result.data == {"transcript_id": "transcript-123"}
