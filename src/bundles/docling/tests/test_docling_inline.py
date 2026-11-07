"""Tests for the inline Docling component's OCR configuration."""

import importlib.util
import io
import json
import sys
import types
from types import SimpleNamespace

import pytest
from lfx_docling.components.docling.docling_inline import DoclingInlineComponent


def test_force_ocr_input_defaults_to_disabled():
    """Keep full-page OCR opt-in for existing flows."""
    force_ocr = next(
        component_input for component_input in DoclingInlineComponent.inputs if component_input.name == "force_ocr"
    )

    assert force_ocr.value is False


def test_process_files_forwards_force_ocr_to_child(monkeypatch, tmp_path):
    """Forward the force option across the subprocess boundary."""
    captured = bytearray()

    class CaptureStdin:
        def write(self, data):
            captured.extend(data)

        def close(self):
            return None

    class FakeProcess:
        def __init__(self, _command, *, stdout, **_kwargs):
            self.stdin = CaptureStdin()
            self.stdout = stdout
            self._finished = False

        def poll(self):
            if not self._finished:
                self.stdout.write(b'{"ok": true, "results": []}')
                self.stdout.flush()
                self._finished = True
            return 0

    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr("lfx_docling.components.docling.docling_inline.subprocess.Popen", FakeProcess)
    monkeypatch.setattr(DoclingInlineComponent, "rollup_data", lambda _self, _files, data: data)

    component = DoclingInlineComponent()
    component.pipeline = "standard"
    component.ocr_engine = "easyocr"
    component.force_ocr = True
    component.do_picture_classification = False
    component.pic_desc_llm = None
    component.pic_desc_prompt = ""

    result = component.process_files([SimpleNamespace(path=tmp_path / "scan.pdf")])

    assert result == []
    assert json.loads(captured)["force_ocr"] is True


def _run_child_script(monkeypatch, capsys, *, pipeline="standard", force_ocr=False):
    """Execute the embedded child script with lightweight Docling stand-ins."""
    created_pipeline_options = []

    class FakePdfPipelineOptions:
        def __init__(self):
            self.do_ocr = False
            self.ocr_options = SimpleNamespace(mode=None)
            created_pipeline_options.append(self)

    class FakePdfFormatOption:
        def __init__(self, **kwargs):
            self.pipeline_options = kwargs.get("pipeline_options")

    class FakeDocumentConverter:
        def __init__(self, **_kwargs):
            return None

    base_models = types.ModuleType("docling.datamodel.base_models")
    base_models.ConversionStatus = SimpleNamespace(SUCCESS="success")
    base_models.InputFormat = SimpleNamespace(PDF="pdf", IMAGE="image")

    pipeline_options = types.ModuleType("docling.datamodel.pipeline_options")
    pipeline_options.OcrMode = SimpleNamespace(FULL_PAGE="full_page")
    pipeline_options.PdfPipelineOptions = FakePdfPipelineOptions

    document_converter = types.ModuleType("docling.document_converter")
    document_converter.DocumentConverter = FakeDocumentConverter
    document_converter.FormatOption = object
    document_converter.PdfFormatOption = FakePdfFormatOption

    for module_name in ("docling", "docling.datamodel"):
        monkeypatch.setitem(sys.modules, module_name, types.ModuleType(module_name))
    monkeypatch.setitem(sys.modules, "docling.datamodel.base_models", base_models)
    monkeypatch.setitem(sys.modules, "docling.datamodel.pipeline_options", pipeline_options)
    monkeypatch.setitem(sys.modules, "docling.document_converter", document_converter)

    config = {
        "file_paths": [],
        "pipeline": pipeline,
        "ocr_engine": "None",
        "force_ocr": force_ocr,
        "do_picture_classification": False,
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(config)))

    exec(DoclingInlineComponent._CHILD_SCRIPT, {"__name__": "__main__"})  # noqa: S102

    return created_pipeline_options, json.loads(capsys.readouterr().out)


def test_child_script_force_ocr_enables_full_page_mode(monkeypatch, capsys):
    """Exercise the child path that implements the new OCR behavior."""
    created_pipeline_options, payload = _run_child_script(monkeypatch, capsys, force_ocr=True)

    assert payload == {"ok": True, "results": []}
    assert len(created_pipeline_options) == 1
    assert created_pipeline_options[0].do_ocr is True
    assert created_pipeline_options[0].ocr_options.mode == "full_page"


def test_process_files_rejects_force_ocr_with_vlm(tmp_path):
    """Reject a force option that the VLM pipeline cannot honor."""
    component = DoclingInlineComponent()
    component.pipeline = "vlm"
    component.force_ocr = True

    with pytest.raises(ValueError, match=r"VLM pipeline.*no separate OCR stage"):
        component.process_files([SimpleNamespace(path=tmp_path / "scan.pdf")])


def test_child_script_rejects_force_ocr_with_vlm(monkeypatch, capsys):
    """Keep the subprocess boundary defensive if it is invoked directly."""
    created_pipeline_options, payload = _run_child_script(
        monkeypatch,
        capsys,
        pipeline="vlm",
        force_ocr=True,
    )

    assert created_pipeline_options == []
    assert payload["ok"] is False
    assert "VLM pipeline" in payload["error"]
