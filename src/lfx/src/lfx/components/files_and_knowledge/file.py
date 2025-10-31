"""Enhanced file component with Docling support and process isolation.

Notes:
-----
- ALL Docling parsing/export runs in a separate OS process to prevent memory
  growth and native library state from impacting the main Langflow process.
- Standard text/structured parsing continues to use existing BaseFileComponent
  utilities (and optional threading via `parallel_load_data`).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from copy import deepcopy
from typing import Any

from lfx.base.data.base_file import BaseFileComponent
from lfx.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from lfx.inputs.inputs import DropdownInput, MessageTextInput, StrInput
from lfx.io import BoolInput, FileInput, IntInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame  # noqa: TC001
from lfx.schema.message import Message


class FileComponent(BaseFileComponent):
    """File component with optional Docling processing (isolated in a subprocess)."""

    display_name = "Read File"
    description = "Loads content from one or more files."
    documentation: str = "https://docs.langflow.org/components-data#file"
    icon = "file-text"
    name = "File"

    # Docling-supported/compatible extensions; TEXT_FILE_TYPES are supported by the base loader.
    VALID_EXTENSIONS = [
        *TEXT_FILE_TYPES,
        "adoc",
        "asciidoc",
        "asc",
        "bmp",
        "dotx",
        "dotm",
        "docm",
        "jpg",
        "jpeg",
        "png",
        "potx",
        "ppsx",
        "pptm",
        "potm",
        "ppsm",
        "pptx",
        "tiff",
        "xls",
        "xlsx",
        "xhtml",
        "webp",
    ]

    # Fixed export settings used when markdown export is requested.
    EXPORT_FORMAT = "Markdown"
    IMAGE_MODE = "placeholder"

    _base_inputs = deepcopy(BaseFileComponent.get_base_inputs())

    for input_item in _base_inputs:
        if isinstance(input_item, FileInput) and input_item.name == "path":
            input_item.real_time_refresh = True
            break

    inputs = [
        *_base_inputs,
        BoolInput(
            name="advanced_mode",
            display_name="Advanced Parser",
            value=False,
            real_time_refresh=True,
            info=(
                "Enable advanced document processing and export with Docling for PDFs, images, and office documents. "
                "Note that advanced document processing can consume significant resources."
            ),
            show=True,
        ),
        DropdownInput(
            name="pipeline",
            display_name="Pipeline",
            info="Docling pipeline to use",
            options=["standard", "vlm"],
            value="standard",
            advanced=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="ocr_engine",
            display_name="OCR Engine",
            info="OCR engine to use. Only available when pipeline is set to 'standard'.",
            options=["None", "easyocr"],
            value="easyocr",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="md_image_placeholder",
            display_name="Image placeholder",
            info="Specify the image placeholder for markdown exports.",
            value="<!-- image -->",
            advanced=True,
            show=False,
        ),
        StrInput(
            name="md_page_break_placeholder",
            display_name="Page break placeholder",
            info="Add this placeholder between pages in the markdown output.",
            value="",
            advanced=True,
            show=False,
        ),
        MessageTextInput(
            name="doc_key",
            display_name="Doc Key",
            info="The key to use for the DoclingDocument column.",
            value="doc",
            advanced=True,
            show=False,
        ),
        # Deprecated input retained for backward-compatibility.
        BoolInput(
            name="use_multithreading",
            display_name="[Deprecated] Use Multithreading",
            advanced=True,
            value=True,
            info="Set 'Processing Concurrency' greater than 1 to enable multithreading.",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=True,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
        BoolInput(
            name="markdown",
            display_name="Markdown Export",
            info="Export processed documents to Markdown format. Only available when advanced mode is enabled.",
            value=False,
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="Raw Content", name="message", method="load_files_message"),
    ]

    # ------------------------------ UI helpers --------------------------------------

    def _path_value(self, template: dict) -> list[str]:
        """Return the list of currently selected file paths from the template."""
        return template.get("path", {}).get("file_path", [])

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Show/hide Advanced Parser and related fields based on selection context."""
        if field_name == "path":
            paths = self._path_value(build_config)

            # If all files can be processed by docling, do so
            allow_advanced = all(not file_path.endswith((".csv", ".xlsx", ".parquet")) for file_path in paths)
            build_config["advanced_mode"]["show"] = allow_advanced
            if not allow_advanced:
                build_config["advanced_mode"]["value"] = False
                for f in ("pipeline", "ocr_engine", "doc_key", "md_image_placeholder", "md_page_break_placeholder"):
                    if f in build_config:
                        build_config[f]["show"] = False

        # Docling Processing
        elif field_name == "advanced_mode":
            for f in ("pipeline", "ocr_engine", "doc_key", "md_image_placeholder", "md_page_break_placeholder"):
                if f in build_config:
                    build_config[f]["show"] = bool(field_value)
                    if f == "pipeline":
                        build_config[f]["advanced"] = not bool(field_value)

        elif field_name == "pipeline":
            if field_value == "standard":
                build_config["ocr_engine"]["show"] = True
                build_config["ocr_engine"]["value"] = "easyocr"
            else:
                build_config["ocr_engine"]["show"] = False
                build_config["ocr_engine"]["value"] = "None"

        return build_config

    def update_outputs(self, frontend_node: dict[str, Any], field_name: str, field_value: Any) -> dict[str, Any]:  # noqa: ARG002
        """Dynamically show outputs based on file count/type and advanced mode."""
        if field_name not in ["path", "advanced_mode", "pipeline"]:
            return frontend_node

        template = frontend_node.get("template", {})
        paths = self._path_value(template)
        if not paths:
            return frontend_node

        frontend_node["outputs"] = []
        if len(paths) == 1:
            file_path = paths[0] if field_name == "path" else frontend_node["template"]["path"]["file_path"][0]
            if file_path.endswith((".csv", ".xlsx", ".parquet")):
                frontend_node["outputs"].append(
                    Output(display_name="Structured Content", name="dataframe", method="load_files_structured"),
                )
            elif file_path.endswith(".json"):
                frontend_node["outputs"].append(
                    Output(display_name="Structured Content", name="json", method="load_files_json"),
                )

            advanced_mode = frontend_node.get("template", {}).get("advanced_mode", {}).get("value", False)
            if advanced_mode:
                frontend_node["outputs"].append(
                    Output(display_name="Structured Output", name="advanced_dataframe", method="load_files_dataframe"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="Markdown", name="advanced_markdown", method="load_files_markdown"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path"),
                )
            else:
                frontend_node["outputs"].append(
                    Output(display_name="Raw Content", name="message", method="load_files_message"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path"),
                )
        else:
            # Multiple files => DataFrame output; advanced parser disabled
            frontend_node["outputs"].append(Output(display_name="Files", name="dataframe", method="load_files"))

        return frontend_node

    # ------------------------------ Core processing ----------------------------------

    def _is_docling_compatible(self, file_path: str) -> bool:
        """Lightweight extension gate for Docling-compatible types."""
        docling_exts = (
            ".adoc",
            ".asciidoc",
            ".asc",
            ".bmp",
            ".csv",
            ".dotx",
            ".dotm",
            ".docm",
            ".docx",
            ".htm",
            ".html",
            ".jpg",
            ".jpeg",
            ".json",
            ".md",
            ".pdf",
            ".png",
            ".potx",
            ".ppsx",
            ".pptm",
            ".potm",
            ".ppsm",
            ".pptx",
            ".tiff",
            ".txt",
            ".xls",
            ".xlsx",
            ".xhtml",
            ".xml",
            ".webp",
        )
        return file_path.lower().endswith(docling_exts)

    def _process_docling_in_subprocess(self, file_path: str) -> Data | None:
        """Run Docling in a separate OS process and map the result to a Data object.

        We avoid multiprocessing pickling by launching `python -c "<script>"` and
        passing JSON config via stdin. The child prints a JSON result to stdout.
        """
        if not file_path:
            return None

        args: dict[str, Any] = {
            "file_path": file_path,
            "markdown": bool(self.markdown),
            "image_mode": str(self.IMAGE_MODE),
            "md_image_placeholder": str(self.md_image_placeholder),
            "md_page_break_placeholder": str(self.md_page_break_placeholder),
            "pipeline": str(self.pipeline),
            "ocr_engine": (
                self.ocr_engine if self.ocr_engine and self.ocr_engine != "None" and self.pipeline != "vlm" else None
            ),
        }

        self.log(f"Starting Docling subprocess for file: {file_path}")
        self.log(args)

        # Child script for isolating the docling processing
        child_script = textwrap.dedent(
            r"""
            import json, sys

            def try_imports():
                try:
                    from docling.datamodel.base_models import ConversionStatus, InputFormat  # type: ignore
                    from docling.document_converter import DocumentConverter  # type: ignore
                    from docling_core.types.doc import ImageRefMode  # type: ignore
                    return ConversionStatus, InputFormat, DocumentConverter, ImageRefMode, "latest"
                except Exception as e:
                    raise e

            def create_converter(strategy, input_format, DocumentConverter, pipeline, ocr_engine):
                # --- Standard PDF/IMAGE pipeline (your existing behavior), with optional OCR ---
                if pipeline == "standard":
                    try:
                        from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
                        from docling.document_converter import PdfFormatOption  # type: ignore

                        pipe = PdfPipelineOptions()
                        pipe.do_ocr = False

                        if ocr_engine:
                            try:
                                from docling.models.factories import get_ocr_factory  # type: ignore
                                pipe.do_ocr = True
                                fac = get_ocr_factory(allow_external_plugins=False)
                                pipe.ocr_options = fac.create_options(kind=ocr_engine)
                            except Exception:
                                # If OCR setup fails, disable it
                                pipe.do_ocr = False

                        fmt = {}
                        if hasattr(input_format, "PDF"):
                            fmt[getattr(input_format, "PDF")] = PdfFormatOption(pipeline_options=pipe)
                        if hasattr(input_format, "IMAGE"):
                            fmt[getattr(input_format, "IMAGE")] = PdfFormatOption(pipeline_options=pipe)

                        return DocumentConverter(format_options=fmt)
                    except Exception:
                        return DocumentConverter()

                # --- Vision-Language Model (VLM) pipeline ---
                if pipeline == "vlm":
                    try:
                        from docling.datamodel.pipeline_options import VlmPipelineOptions
                        from docling.datamodel.vlm_model_specs import GRANITEDOCLING_MLX, GRANITEDOCLING_TRANSFORMERS
                        from docling.document_converter import PdfFormatOption
                        from docling.pipeline.vlm_pipeline import VlmPipeline

                        vl_pipe = VlmPipelineOptions(
                            vlm_options=GRANITEDOCLING_TRANSFORMERS,
                        )

                        if sys.platform == "darwin":
                            try:
                                import mlx_vlm
                                vl_pipe.vlm_options = GRANITEDOCLING_MLX
                            except ImportError as e:
                                raise e

                        # VLM paths generally don't need OCR; keep OCR off by default here.
                        fmt = {}
                        if hasattr(input_format, "PDF"):
                            fmt[getattr(input_format, "PDF")] = PdfFormatOption(
                            pipeline_cls=VlmPipeline,
                            pipeline_options=vl_pipe
                        )
                        if hasattr(input_format, "IMAGE"):
                            fmt[getattr(input_format, "IMAGE")] = PdfFormatOption(
                            pipeline_cls=VlmPipeline,
                            pipeline_options=vl_pipe
                        )

                        return DocumentConverter(format_options=fmt)
                    except Exception as e:
                        raise e

                # --- Fallback: default converter with no special options ---
                return DocumentConverter()

            def export_markdown(document, ImageRefMode, image_mode, img_ph, pg_ph):
                try:
                    mode = getattr(ImageRefMode, image_mode.upper(), image_mode)
                    return document.export_to_markdown(
                        image_mode=mode,
                        image_placeholder=img_ph,
                        page_break_placeholder=pg_ph,
                    )
                except Exception:
                    try:
                        return document.export_to_text()
                    except Exception:
                        return str(document)

            def to_rows(doc_dict):
                rows = []
                for t in doc_dict.get("texts", []):
                    prov = t.get("prov") or []
                    page_no = None
                    if prov and isinstance(prov, list) and isinstance(prov[0], dict):
                        page_no = prov[0].get("page_no")
                    rows.append({
                        "page_no": page_no,
                        "label": t.get("label"),
                        "text": t.get("text"),
                        "level": t.get("level"),
                    })
                return rows

            def main():
                cfg = json.loads(sys.stdin.read())
                file_path = cfg["file_path"]
                markdown = cfg["markdown"]
                image_mode = cfg["image_mode"]
                img_ph = cfg["md_image_placeholder"]
                pg_ph = cfg["md_page_break_placeholder"]
                pipeline = cfg["pipeline"]
                ocr_engine = cfg.get("ocr_engine")
                meta = {"file_path": file_path}

                try:
                    ConversionStatus, InputFormat, DocumentConverter, ImageRefMode, strategy = try_imports()
                    converter = create_converter(strategy, InputFormat, DocumentConverter, pipeline, ocr_engine)
                    try:
                        res = converter.convert(file_path)
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"Docling conversion error: {e}", "meta": meta}))
                        return

                    ok = False
                    if hasattr(res, "status"):
                        try:
                            ok = (res.status == ConversionStatus.SUCCESS) or (str(res.status).lower() == "success")
                        except Exception:
                            ok = (str(res.status).lower() == "success")
                    if not ok and hasattr(res, "document"):
                        ok = getattr(res, "document", None) is not None
                    if not ok:
                        print(json.dumps({"ok": False, "error": "Docling conversion failed", "meta": meta}))
                        return

                    doc = getattr(res, "document", None)
                    if doc is None:
                        print(json.dumps({"ok": False, "error": "Docling produced no document", "meta": meta}))
                        return

                    if markdown:
                        text = export_markdown(doc, ImageRefMode, image_mode, img_ph, pg_ph)
                        print(json.dumps({"ok": True, "mode": "markdown", "text": text, "meta": meta}))
                        return

                    # structured
                    try:
                        doc_dict = doc.export_to_dict()
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"Docling export_to_dict failed: {e}", "meta": meta}))
                        return

                    rows = to_rows(doc_dict)
                    print(json.dumps({"ok": True, "mode": "structured", "doc": rows, "meta": meta}))
                except Exception as e:
                    print(
                        json.dumps({
                            "ok": False,
                            "error": f"Docling processing error: {e}",
                            "meta": {"file_path": file_path},
                        })
                    )

            if __name__ == "__main__":
                main()
            """
        )

        # Validate file_path to avoid command injection or unsafe input
        if not isinstance(args["file_path"], str) or any(c in args["file_path"] for c in [";", "|", "&", "$", "`"]):
            return Data(data={"error": "Unsafe file path detected.", "file_path": args["file_path"]})

        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-u", "-c", child_script],
            input=json.dumps(args).encode("utf-8"),
            capture_output=True,
            check=False,
        )

        if not proc.stdout:
            err_msg = proc.stderr.decode("utf-8", errors="replace") or "no output from child process"
            return Data(data={"error": f"Docling subprocess error: {err_msg}", "file_path": file_path})

        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            err_msg = proc.stderr.decode("utf-8", errors="replace")
            return Data(
                data={"error": f"Invalid JSON from Docling subprocess: {e}. stderr={err_msg}", "file_path": file_path},
            )

        if not result.get("ok"):
            return Data(data={"error": result.get("error", "Unknown Docling error"), **result.get("meta", {})})

        meta = result.get("meta", {})
        if result.get("mode") == "markdown":
            exported_content = str(result.get("text", ""))
            return Data(
                text=exported_content,
                data={"exported_content": exported_content, "export_format": self.EXPORT_FORMAT, **meta},
            )

        rows = list(result.get("doc", []))
        return Data(data={"doc": rows, "export_format": self.EXPORT_FORMAT, **meta})

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Process input files.

        - advanced_mode => Docling in a separate process.
        - Otherwise => standard parsing in current process (optionally threaded).
        """
        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        def process_file_standard(file_path: str, *, silent_errors: bool = False) -> Data | None:
            try:
                return parse_text_file_to_data(file_path, silent_errors=silent_errors)
            except FileNotFoundError as e:
                self.log(f"File not found: {file_path}. Error: {e}")
                if not silent_errors:
                    raise
                return None
            except Exception as e:
                self.log(f"Unexpected error processing {file_path}: {e}")
                if not silent_errors:
                    raise
                return None

        docling_compatible = all(self._is_docling_compatible(str(f.path)) for f in file_list)

        # Advanced path: Check if ALL files are compatible with Docling
        if self.advanced_mode and docling_compatible:
            final_return: list[BaseFileComponent.BaseFile] = []
            for file in file_list:
                file_path = str(file.path)
                advanced_data: Data | None = self._process_docling_in_subprocess(file_path)

                # --- UNNEST: expand each element in `doc` to its own Data row
                payload = getattr(advanced_data, "data", {}) or {}
                doc_rows = payload.get("doc")
                if isinstance(doc_rows, list):
                    rows: list[Data | None] = [
                        Data(
                            data={
                                "file_path": file_path,
                                **(item if isinstance(item, dict) else {"value": item}),
                            },
                        )
                        for item in doc_rows
                    ]
                    final_return.extend(self.rollup_data(file_list, rows))
                else:
                    # If not structured, keep as-is (e.g., markdown export or error dict)
                    final_return.extend(self.rollup_data(file_list, [advanced_data]))
            return final_return

        # Standard multi-file (or single non-advanced) path
        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_paths = [str(f.path) for f in file_list]
        self.log(f"Starting parallel processing of {len(file_paths)} files with concurrency: {concurrency}.")
        my_data = parallel_load_data(
            file_paths,
            silent_errors=self.silent_errors,
            load_function=process_file_standard,
            max_concurrency=concurrency,
        )
        return self.rollup_data(file_list, my_data)

    # ------------------------------ Output helpers -----------------------------------

    def load_files_helper(self) -> DataFrame:
        result = self.load_files()

        # Error condition - raise error if no text and an error is present
        if not hasattr(result, "text"):
            if hasattr(result, "error"):
                raise ValueError(result.error[0])
            msg = "Could not extract content from the provided file(s)."
            raise ValueError(msg)

        return result

    def load_files_dataframe(self) -> DataFrame:
        """Load files using advanced Docling processing and export to DataFrame format."""
        self.markdown = False
        return self.load_files_helper()

    def load_files_markdown(self) -> Message:
        """Load files using advanced Docling processing and export to Markdown format."""
        self.markdown = True
        result = self.load_files_helper()
        return Message(text=str(result.text[0]))
