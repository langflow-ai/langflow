from __future__ import annotations

import sys
from contextlib import suppress
from importlib import import_module
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from lfx.log.logger import configure
from lfx.schema.data import Data

_PARENT_MODULE = "lfx_bundles.assemblyai"
_MODULE_NAMES = (
    "lfx_bundles.assemblyai.assemblyai_get_subtitles",
    "lfx_bundles.assemblyai.assemblyai_lemur",
    "lfx_bundles.assemblyai.assemblyai_list_transcripts",
    "lfx_bundles.assemblyai.assemblyai_poll_transcript",
)
_MISSING = object()

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def assemblyai_modules() -> dict[str, ModuleType]:
    parent_module = import_module(_PARENT_MODULE)
    previous_assemblyai = sys.modules.get("assemblyai")
    previous_modules = {name: sys.modules.pop(name, None) for name in _MODULE_NAMES}
    previous_attrs = {
        name.rsplit(".", 1)[-1]: getattr(parent_module, name.rsplit(".", 1)[-1], _MISSING) for name in _MODULE_NAMES
    }
    sys.modules["assemblyai"] = MagicMock()
    try:
        yield {name.rsplit(".", 1)[-1]: import_module(name) for name in _MODULE_NAMES}
    finally:
        if previous_assemblyai is None:
            sys.modules.pop("assemblyai", None)
        else:
            sys.modules["assemblyai"] = previous_assemblyai
        for name, mod in previous_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        for attr, val in previous_attrs.items():
            if val is _MISSING:
                with suppress(AttributeError):
                    delattr(parent_module, attr)
            else:
                setattr(parent_module, attr, val)


def test_list_transcripts_handles_str_created_on_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_list_transcripts"]
    captured_params: list[tuple[int | None, str | None, str | None]] = []

    class _FakeParams:
        def __init__(self) -> None:
            self.limit: int | None = None
            self.status: str | None = None
            self.created_on: str | None = None
            self.before_id: str | None = None
            self.throttled_only: bool | None = None

    class _FakeItem:
        def __init__(self, tid: str) -> None:
            self._tid = tid

        def dict(self) -> dict[str, str]:
            return {"id": self._tid}

    pages = [
        SimpleNamespace(
            transcripts=[_FakeItem("t1")],
            page_details=SimpleNamespace(before_id_of_prev_url="cursor-1"),
        ),
        SimpleNamespace(
            transcripts=[_FakeItem("t2")],
            page_details=SimpleNamespace(before_id_of_prev_url=None),
        ),
    ]

    class _FakeTranscriber:
        def list_transcripts(self, params: _FakeParams) -> SimpleNamespace:
            captured_params.append((params.limit, params.created_on, params.before_id))
            return pages.pop(0)

    monkeypatch.setattr(mod.aai, "ListTranscriptParameters", _FakeParams)
    monkeypatch.setattr(mod.aai, "Transcriber", _FakeTranscriber)

    component = mod.AssemblyAIListTranscripts(
        api_key="test-key",  # pragma: allowlist secret
        limit=0,
        created_on=" 2026-11-25 ",
    )
    result = component.list_transcripts()

    assert [item.data for item in result] == [{"id": "t1"}, {"id": "t2"}]
    assert captured_params == [
        (100, "2026-11-25", None),
        (100, "2026-11-25", "cursor-1"),
    ]


def test_list_transcripts_returns_error_data_on_invalid_limit(
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_list_transcripts"]
    component = mod.AssemblyAIListTranscripts(
        api_key="test-key",  # pragma: allowlist secret
        limit=-1,
    )
    result = component.list_transcripts()

    assert len(result) == 1
    assert "Limit must be 0 or greater" in result[0].data["error"]


def test_lemur_prefers_explicit_transcript_ids_and_logs_safely_at_info_level(
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_lemur"]
    configure(log_level="INFO", cache=False)
    try:
        captured_ids: list[list[str]] = []
        captured_questions: list[list[str]] = []

        class _FakeLemurResult:
            def dict(self) -> dict[str, str]:
                return {"response": "ok"}

        class _FakeLemur:
            def question(self, *, questions: list[SimpleNamespace], **_kwargs: object) -> _FakeLemurResult:
                captured_questions.append([q.question for q in questions])
                return _FakeLemurResult()

        class _FakeTranscriptGroup:
            def __init__(self, *, transcript_ids: list[str]) -> None:
                captured_ids.append(transcript_ids)
                self.transcripts = [SimpleNamespace(status="completed", error=None)]
                self.lemur = _FakeLemur()

            def wait_for_completion(self, *, return_failures: bool = False) -> tuple[_FakeTranscriptGroup, list[str]]:
                assert return_failures is True
                return self, []

        monkeypatch.setattr(mod.aai, "TranscriptGroup", _FakeTranscriptGroup)
        monkeypatch.setattr(mod.aai, "TranscriptStatus", SimpleNamespace(error="error", completed="completed"))
        monkeypatch.setattr(mod.aai, "LemurQuestion", lambda *, question: SimpleNamespace(question=question))
        monkeypatch.setattr(mod.aai, "LemurModel", SimpleNamespace(claude3_5_sonnet="claude3_5_sonnet"))

        component = mod.AssemblyAILeMUR(
            api_key="test-key",  # pragma: allowlist secret
            transcription_result=Data(data={"error": "upstream error", "id": "ignored-id"}),
            transcript_ids=" t1, , t2 ",
            endpoint="question-answer",
            questions=" What happened? , Who spoke? , ",
            prompt="unused",
        )
        result = component.run_lemur()

        assert captured_ids == [["t1", "t2"]]
        assert captured_questions == [["What happened?", "Who spoke?"]]
        assert result.data == {"response": "ok"}
    finally:
        configure(log_level="CRITICAL", cache=False)


def test_lemur_catches_transcript_group_errors_and_blank_questions(
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_lemur"]

    blank_q = mod.AssemblyAILeMUR(
        api_key="test-key",  # pragma: allowlist secret
        transcription_result=Data(data={"id": "t1"}),
        endpoint="question-answer",
        questions=" , , ",
        prompt="unused",
    )
    assert blank_q.run_lemur().data == {"error": "No Questions were provided for the question-answer endpoint"}

    def _boom(**_kwargs: object) -> None:
        msg = "network failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(mod.aai, "TranscriptGroup", _boom)
    failing = mod.AssemblyAILeMUR(
        api_key="test-key",  # pragma: allowlist secret
        transcription_result=Data(data={"id": "t1"}),
        endpoint="summary",
        prompt="unused",
    )
    assert failing.run_lemur().data == {"error": "Getting transcriptions failed: network failure"}


def test_get_subtitles_handles_export_exception_and_missing_error(
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_get_subtitles"]
    monkeypatch.setattr(mod.aai, "TranscriptStatus", SimpleNamespace(completed="completed", error="error"))

    class _FailingExportTranscript:
        status = "completed"
        error = None

        def export_subtitles_srt(self, _chars: int | None) -> str:
            msg = "export failed"
            raise RuntimeError(msg)

    monkeypatch.setattr(mod.aai.Transcript, "get_by_id", lambda _tid: _FailingExportTranscript())
    comp = mod.AssemblyAIGetSubtitles(
        api_key="test-key",  # pragma: allowlist secret
        transcription_result=Data(data={"id": "t1"}),
        subtitle_format="srt",
    )
    assert comp.get_subtitles().data == {"error": "Exporting subtitles failed: export failed"}

    non_completed = SimpleNamespace(status="processing", error=None)
    monkeypatch.setattr(mod.aai.Transcript, "get_by_id", lambda _tid: non_completed)
    assert comp.get_subtitles().data == {"error": "Transcription ended with status: processing"}


def test_poll_transcript_orders_fields_and_handles_missing_error(
    monkeypatch: pytest.MonkeyPatch,
    assemblyai_modules: dict[str, ModuleType],
) -> None:
    mod = assemblyai_modules["assemblyai_poll_transcript"]
    monkeypatch.setattr(mod.aai, "TranscriptStatus", SimpleNamespace(completed="completed", error="error"))

    completed = SimpleNamespace(
        status="completed",
        error=None,
        json_response={"id": "t1", "text": "hello", "utterances": [{"text": "hello"}], "language_code": "en"},
    )
    monkeypatch.setattr(mod.aai.Transcript, "get_by_id", lambda _tid: completed)
    comp = mod.AssemblyAITranscriptionJobPoller(
        api_key="test-key",  # pragma: allowlist secret
        transcript_id=Data(data={"transcript_id": "t1"}),
    )
    res = comp.poll_transcription_job()
    assert list(res.data.keys())[:3] == ["text", "utterances", "id"]
    assert res.data["language_code"] == "en"

    non_completed = SimpleNamespace(status="error", error=None)
    monkeypatch.setattr(mod.aai.Transcript, "get_by_id", lambda _tid: non_completed)
    assert comp.poll_transcription_job().data == {"error": "Transcription ended with status: error"}
