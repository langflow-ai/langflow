"""Exercise both isolated Docling workers without loading the OCR model stack."""

import ast
import contextlib
import io
import json
import subprocess
import sys
import textwrap
import time
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
    msg = f"Worker script {variable_name} not found in {source}"
    raise AssertionError(msg)


def _fake_docling_modules(*, ocr_setup_error: str | None = None) -> dict[str, types.ModuleType]:
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

    def get_ocr_factory(**_kwargs):
        if ocr_setup_error == "factory":
            msg = "OCR factory unavailable"
            raise RuntimeError(msg)

        def create_options(**_kwargs):
            if ocr_setup_error == "options":
                msg = "OCR options unavailable"
                raise RuntimeError(msg)
            return types.SimpleNamespace(force_full_page_ocr=False)

        return types.SimpleNamespace(create_options=create_options)

    modules["docling.models.factories"].get_ocr_factory = get_ocr_factory
    modules["docling_core.types.doc"].ImageRefMode = types.SimpleNamespace(PLACEHOLDER="placeholder")
    return modules


def _run_worker(script: str, config: dict, *, ocr_setup_error: str | None = None) -> dict:
    output = io.StringIO()
    with (
        patch.dict(sys.modules, _fake_docling_modules(ocr_setup_error=ocr_setup_error)),
        patch("sys.stdin", io.StringIO(json.dumps(config))),
        contextlib.redirect_stdout(output),
    ):
        exec(script, {"__name__": "__main__"})  # noqa: S102 - executes the checked-in worker source
    return json.loads(output.getvalue().strip())


def _parent_method(source: Path, class_name: str, method_name: str, namespace: dict):
    """Execute the checked-in parent method without importing the optional Docling stack."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    component = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in component.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    method.decorator_list = []
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)  # noqa: S102
    return namespace[method_name]


class _ConfigCapturedError(Exception):
    """Stop the parent method once it has sent its configuration to the child."""


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
                assert result["ok"]
                assert result["results"][0]["document"]["texts"][0]["text"] == f"force={force_ocr}"

        result = _run_worker(script, {**config, "force_ocr": True, "ocr_engine": "None"})
        assert not result["ok"]
        assert "requires the standard pipeline and an OCR engine" in result["error"]

        result = _run_worker(script, {**config, "force_ocr": True, "pipeline": "vlm"})
        assert not result["ok"]
        assert "requires the standard pipeline and an OCR engine" in result["error"]

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
                assert result["ok"]
                assert result["doc"][0]["text"] == f"force={force_ocr}"

        result = _run_worker(script, {**config, "force_ocr": True, "pipeline": "vlm"})
        assert not result["ok"]
        assert "requires the standard pipeline and an OCR engine" in result["error"]

        result = _run_worker(script, {**config, "force_ocr": True, "ocr_engine": None})
        assert not result["ok"]
        assert "requires the standard pipeline and an OCR engine" in result["error"]

    def test_forced_ocr_reports_setup_errors_in_both_workers(self):
        for source, variable_name, config in (
            (
                INLINE_SOURCE,
                "_CHILD_SCRIPT",
                {
                    "file_paths": ["sample.pdf"],
                    "pipeline": "standard",
                    "ocr_engine": "easyocr",
                    "do_picture_classification": False,
                },
            ),
            (
                FILE_SOURCE,
                "child_script",
                {
                    "file_path": "sample.pdf",
                    "markdown": False,
                    "image_mode": "placeholder",
                    "md_image_placeholder": "",
                    "md_page_break_placeholder": "",
                    "pipeline": "standard",
                    "ocr_engine": "easyocr",
                },
            ),
        ):
            script = _worker_script(source, variable_name)
            for failure, message in (("factory", "OCR factory unavailable"), ("options", "OCR options unavailable")):
                with self.subTest(source=source.name, failure=failure):
                    result = _run_worker(script, {**config, "force_ocr": True}, ocr_setup_error=failure)
                    assert not result["ok"]
                    assert message in result["error"]


class TestDoclingForceOcrParentConfig(unittest.TestCase):
    def test_inline_component_sends_force_ocr_to_child(self):
        captured = []

        def capture(data):
            captured.append(json.loads(data))
            raise _ConfigCapturedError

        method = _parent_method(
            INLINE_SOURCE,
            "DoclingInlineComponent",
            "process_files",
            {"subprocess": subprocess, "sys": sys, "json": json, "time": time},
        )
        component = types.SimpleNamespace(
            pic_desc_llm=None,
            pipeline="standard",
            ocr_engine="easyocr",
            do_picture_classification=False,
            pic_desc_prompt="",
            _CHILD_SCRIPT="",
        )
        process = types.SimpleNamespace(stdin=types.SimpleNamespace(write=capture))
        for force_ocr in (False, True):
            with self.subTest(force_ocr=force_ocr):
                component.force_ocr = force_ocr
                with (
                    patch("importlib.util.find_spec", return_value=object()),
                    patch("subprocess.Popen", return_value=process),
                ):
                    try:
                        method(component, [types.SimpleNamespace(path="sample.pdf")])
                    except _ConfigCapturedError:
                        pass
                    else:
                        self.fail("Child process did not receive a configuration")
                assert captured[-1]["force_ocr"] is force_ocr

    def test_file_component_sends_force_ocr_to_child(self):
        captured = []

        def capture(**kwargs):
            captured.append(json.loads(kwargs["input"]))
            raise _ConfigCapturedError

        method = _parent_method(
            FILE_SOURCE,
            "FileComponent",
            "_process_docling_subprocess_impl",
            {
                "subprocess": subprocess,
                "sys": sys,
                "json": json,
                "time": time,
                "textwrap": textwrap,
                "_FILE_TOOL_CANCEL_EVENT": types.SimpleNamespace(get=lambda: None),
                "_raise_if_file_tool_cancelled": lambda _event=None: None,
            },
        )
        component = types.SimpleNamespace(
            markdown=False,
            IMAGE_MODE="placeholder",
            md_image_placeholder="",
            md_page_break_placeholder="",
            pipeline="standard",
            ocr_engine="easyocr",
        )
        process = types.SimpleNamespace(communicate=capture, poll=lambda: 0)
        for force_ocr in (False, True):
            with self.subTest(force_ocr=force_ocr):
                component.force_ocr = force_ocr
                with patch("subprocess.Popen", return_value=process):
                    try:
                        method(component, "sample.pdf", "sample.pdf")
                    except _ConfigCapturedError:
                        pass
                    else:
                        self.fail("Child process did not receive a configuration")
                assert captured[-1]["force_ocr"] is force_ocr
