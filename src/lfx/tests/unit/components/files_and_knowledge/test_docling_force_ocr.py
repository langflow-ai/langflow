"""Exercise both isolated Docling workers without loading the OCR model stack."""

import ast
import contextlib
import io
import json
import sys
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[6]
INLINE_SOURCE = ROOT / "src/bundles/docling/src/lfx_docling/components/docling/docling_inline.py"
FILE_SOURCE = ROOT / "src/lfx/src/lfx/components/files_and_knowledge/file.py"


def _worker_script(source: Path, variable_name: str) -> str:
    """Read the script that production sends to its child Python process."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        if variable_name in names:
            return textwrap.dedent(node.value.args[0].value)
    raise AssertionError(f"Worker script {variable_name} not found in {source}")


def _fake_docling_modules() -> dict[str, types.ModuleType]:
    modules = {}
    for name in (
        "docling",
        "docling.datamodel",
        "docling.datamodel.base_models",
        "docling.datamodel.pipeline_options",
        "docling.document_converter",
        "docling.models",
        "docling.models.factories",
        "docling_core",
        "docling_core.types",
        "docling_core.types.doc",
    ):
        module = types.ModuleType(name)
        module.__path__ = []
        modules[name] = module

    class InputFormat:
        PDF = "PDF"
        IMAGE = "IMAGE"

    class PdfPipelineOptions:
        def __init__(self):
            self.do_ocr = False
            self.ocr_options = types.SimpleNamespace(force_full_page_ocr=False)

    class PdfFormatOption:
        def __init__(self, *, pipeline_options=None, **_kwargs):
            self.pipeline_options = pipeline_options

    class DocumentConverter:
        def __init__(self, *, format_options=None):
            self.format_options = format_options or {}

        def convert(self, _file_path):
            options = self.format_options[InputFormat.PDF].pipeline_options
            force_ocr = options.ocr_options.force_full_page_ocr
            document = types.SimpleNamespace(
                name=None,
                origin=None,
                export_to_dict=lambda: {"texts": [{"text": f"force={force_ocr}"}]},
            )
            return types.SimpleNamespace(status="SUCCESS", document=document)

    modules["docling.datamodel.base_models"].ConversionStatus = types.SimpleNamespace(SUCCESS="SUCCESS")
    modules["docling.datamodel.base_models"].InputFormat = InputFormat
    modules["docling.datamodel.pipeline_options"].PdfPipelineOptions = PdfPipelineOptions
    modules["docling.document_converter"].DocumentConverter = DocumentConverter
    modules["docling.document_converter"].FormatOption = object
    modules["docling.document_converter"].PdfFormatOption = PdfFormatOption
    modules["docling.models.factories"].get_ocr_factory = lambda **_kwargs: types.SimpleNamespace(
        create_options=lambda **_kwargs: types.SimpleNamespace(force_full_page_ocr=False)
    )
    modules["docling_core.types.doc"].ImageRefMode = types.SimpleNamespace(PLACEHOLDER="placeholder")
    return modules


def _run_worker(script: str, config: dict) -> dict:
    output = io.StringIO()
    with (
        patch.dict(sys.modules, _fake_docling_modules()),
        patch("sys.stdin", io.StringIO(json.dumps(config))),
        contextlib.redirect_stdout(output),
    ):
        exec(script, {"__name__": "__main__"})  # noqa: S102 - executes the checked-in worker source
    return json.loads(output.getvalue().strip())


class TestDoclingForceOcrWorkers(unittest.TestCase):
    def test_inline_worker_passes_full_page_setting_to_docling(self):
        script = _worker_script(INLINE_SOURCE, "_CHILD_SCRIPT")
        config = {
            "file_paths": ["sample.pdf"],
            "pipeline": "standard",
            "ocr_engine": "easyocr",
            "do_picture_classification": False,
        }
        for force_ocr in (False, True):
            with self.subTest(force_ocr=force_ocr):
                result = _run_worker(script, {**config, "force_ocr": force_ocr})
                self.assertTrue(result["ok"])
                self.assertEqual(result["results"][0]["document"]["texts"][0]["text"], f"force={force_ocr}")

        result = _run_worker(script, {**config, "force_ocr": True, "ocr_engine": "None"})
        self.assertFalse(result["ok"])
        self.assertIn("requires the standard pipeline and an OCR engine", result["error"])

        result = _run_worker(script, {**config, "force_ocr": True, "pipeline": "vlm"})
        self.assertFalse(result["ok"])
        self.assertIn("requires the standard pipeline and an OCR engine", result["error"])

    def test_file_worker_passes_full_page_setting_to_docling(self):
        script = _worker_script(FILE_SOURCE, "child_script")
        config = {
            "file_path": "sample.pdf",
            "markdown": False,
            "image_mode": "placeholder",
            "md_image_placeholder": "",
            "md_page_break_placeholder": "",
            "pipeline": "standard",
            "ocr_engine": "easyocr",
        }
        for force_ocr in (False, True):
            with self.subTest(force_ocr=force_ocr):
                result = _run_worker(script, {**config, "force_ocr": force_ocr})
                self.assertTrue(result["ok"])
                self.assertEqual(result["doc"][0]["text"], f"force={force_ocr}")

        result = _run_worker(script, {**config, "force_ocr": True, "pipeline": "vlm"})
        self.assertFalse(result["ok"])
        self.assertIn("requires the standard pipeline and an OCR engine", result["error"])

        result = _run_worker(script, {**config, "force_ocr": True, "ocr_engine": None})
        self.assertFalse(result["ok"])
        self.assertIn("requires the standard pipeline and an OCR engine", result["error"])
