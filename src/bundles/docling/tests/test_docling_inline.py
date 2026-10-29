import importlib.util
import json
from types import SimpleNamespace

from lfx_docling.components.docling.docling_inline import DoclingInlineComponent


def test_force_ocr_input_defaults_to_disabled():
    force_ocr = next(
        component_input for component_input in DoclingInlineComponent.inputs if component_input.name == "force_ocr"
    )

    assert force_ocr.value is False


def test_process_files_forwards_force_ocr_to_child(monkeypatch, tmp_path):
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
