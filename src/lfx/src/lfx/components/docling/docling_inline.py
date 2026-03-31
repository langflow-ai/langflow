import json
import subprocess
import sys
import textwrap
import time

from lfx.base.data import BaseFileComponent
from lfx.base.data.docling_utils import _serialize_pydantic_model
from lfx.inputs import BoolInput, DropdownInput, HandleInput, StrInput
from lfx.schema import Data


class DoclingInlineComponent(BaseFileComponent):
    display_name = "Docling"
    description = "Uses Docling to process input documents running the Docling models locally."
    documentation = "https://docling-project.github.io/docling/"
    trace_type = "tool"
    icon = "Docling"
    name = "DoclingInline"

    # https://docling-project.github.io/docling/usage/supported_formats/
    VALID_EXTENSIONS = [
        "adoc",
        "asciidoc",
        "asc",
        "bmp",
        "csv",
        "dotx",
        "dotm",
        "docm",
        "docx",
        "htm",
        "html",
        "jpeg",
        "json",
        "md",
        "pdf",
        "png",
        "potx",
        "ppsx",
        "pptm",
        "potm",
        "ppsm",
        "pptx",
        "tiff",
        "txt",
        "xls",
        "xlsx",
        "xhtml",
        "xml",
        "webp",
    ]

    inputs = [
        *BaseFileComponent.get_base_inputs(),
        DropdownInput(
            name="pipeline",
            display_name="Pipeline",
            info="Docling pipeline to use",
            options=["standard", "vlm"],
            value="standard",
        ),
        DropdownInput(
            name="ocr_engine",
            display_name="OCR Engine",
            info="OCR engine to use. None will disable OCR.",
            options=["None", "easyocr", "tesserocr", "rapidocr", "ocrmac"],
            value="None",
        ),
        BoolInput(
            name="do_picture_classification",
            display_name="Picture classification",
            info="If enabled, the Docling pipeline will classify the pictures type.",
            value=False,
        ),
        HandleInput(
            name="pic_desc_llm",
            display_name="Picture description LLM",
            info="If connected, the model to use for running the picture description task.",
            input_types=["LanguageModel"],
            required=False,
        ),
        StrInput(
            name="pic_desc_prompt",
            display_name="Picture description prompt",
            value="Describe the image in three sentences. Be concise and accurate.",
            info="The user prompt to use when invoking the model.",
            advanced=True,
        ),
        # TODO: expose more Docling options
    ]

    outputs = [
        *BaseFileComponent.get_base_outputs(),
    ]

    # ------------------------------------------------------------------ #
    # Child script that runs Docling in a separate OS process.            #
    # Uses subprocess.Popen (same pattern as Read File advanced mode)     #
    # instead of multiprocessing/threading so that:                       #
    #   1. It works reliably under Gunicorn's fork-based workers          #
    #   2. The parent's event loop stays free for SSE heartbeats          #
    #   3. No pickling / signal-handler conflicts                         #
    # ------------------------------------------------------------------ #
    _CHILD_SCRIPT: str = textwrap.dedent(r"""
        import json, sys

        def main():
            cfg = json.loads(sys.stdin.read())
            file_paths      = cfg["file_paths"]
            pipeline        = cfg["pipeline"]
            ocr_engine      = cfg["ocr_engine"]
            do_picture_cls  = cfg["do_picture_classification"]
            pic_desc_config = cfg.get("pic_desc_config")
            pic_desc_prompt = cfg.get("pic_desc_prompt", "")

            try:
                from docling.datamodel.base_models import ConversionStatus, InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
            except ImportError as e:
                print(json.dumps({"ok": False, "error": f"Docling is not installed: {e}"}))
                return

            # --- build converter ------------------------------------------------
            try:
                pipe = PdfPipelineOptions()
                pipe.do_ocr = ocr_engine not in ("", "None")
                if pipe.do_ocr:
                    try:
                        from docling.models.factories import get_ocr_factory
                        fac = get_ocr_factory(allow_external_plugins=False)
                        pipe.ocr_options = fac.create_options(kind=ocr_engine)
                    except Exception:
                        pipe.do_ocr = False

                pipe.do_picture_classification = do_picture_cls

                if pic_desc_config:
                    try:
                        import importlib
                        from pydantic import TypeAdapter
                        from langchain_docling.picture_description import (
                            PictureDescriptionLangChainOptions,
                        )
                        mod_name, cls_name = pic_desc_config["__class_path__"].rsplit(".", 1)
                        mod = importlib.import_module(mod_name)
                        cls = getattr(mod, cls_name)
                        adapter = TypeAdapter(cls)
                        llm = adapter.validate_python(pic_desc_config["config"])
                        pipe.do_picture_description = True
                        pipe.allow_external_plugins = True
                        pipe.picture_description_options = PictureDescriptionLangChainOptions(
                            llm=llm, prompt=pic_desc_prompt,
                        )
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"Picture description setup failed: {e}"}))
                        return

                if pipeline == "vlm":
                    try:
                        from docling.datamodel.pipeline_options import VlmPipelineOptions
                        from docling.pipeline.vlm_pipeline import VlmPipeline
                        vlm_opts = VlmPipelineOptions()
                        if sys.platform == "darwin":
                            try:
                                from docling.datamodel.vlm_model_specs import GRANITEDOCLING_MLX
                                vlm_opts.vlm_options = GRANITEDOCLING_MLX
                            except ImportError:
                                from docling.datamodel.vlm_model_specs import GRANITEDOCLING_TRANSFORMERS
                                vlm_opts.vlm_options = GRANITEDOCLING_TRANSFORMERS
                        fmt = {}
                        if hasattr(InputFormat, "PDF"):
                            fmt[InputFormat.PDF] = PdfFormatOption(
                                pipeline_cls=VlmPipeline, pipeline_options=vlm_opts,
                            )
                        if hasattr(InputFormat, "IMAGE"):
                            fmt[InputFormat.IMAGE] = PdfFormatOption(
                                pipeline_cls=VlmPipeline, pipeline_options=vlm_opts,
                            )
                        converter = DocumentConverter(format_options=fmt)
                    except Exception as e:
                        print(json.dumps({"ok": False, "error": f"VLM pipeline setup failed: {e}"}))
                        return
                else:
                    pdf_opt = PdfFormatOption(pipeline_options=pipe)
                    fmt = {}
                    if hasattr(InputFormat, "PDF"):
                        fmt[InputFormat.PDF] = pdf_opt
                    if hasattr(InputFormat, "IMAGE"):
                        fmt[InputFormat.IMAGE] = pdf_opt
                    converter = DocumentConverter(format_options=fmt)
            except Exception as e:
                print(json.dumps({"ok": False, "error": f"Converter creation failed: {e}"}))
                return

            # --- process files --------------------------------------------------
            results = []
            for fp in file_paths:
                try:
                    res = converter.convert(fp)
                    ok = False
                    if hasattr(res, "status"):
                        try:
                            ok = res.status == ConversionStatus.SUCCESS
                        except Exception:
                            ok = str(res.status).lower() == "success"
                    if not ok and getattr(res, "document", None) is not None:
                        ok = True
                    if ok and res.document is not None:
                        doc_json = res.document.export_to_dict()
                        results.append({
                            "document": doc_json,
                            "file_path": str(fp),
                            "status": "SUCCESS",
                        })
                    else:
                        results.append(None)
                except Exception as e:
                    sys.stderr.write(f"Error processing {fp}: {e}\n")
                    results.append(None)

            print(json.dumps({"ok": True, "results": results}))

        if __name__ == "__main__":
            main()
    """)

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        # Check that docling is installed without actually importing it.
        # The real import (PyTorch, transformers, etc.) happens in the child
        # subprocess.  Importing it here would spike memory and get the
        # Gunicorn worker SIGKILL'd by the OOM killer.
        import importlib.util

        if importlib.util.find_spec("docling") is None:
            msg = (
                "Docling is an optional dependency. Install with `uv pip install 'langflow[docling]'` or refer to the "
                "documentation on how to install optional dependencies."
            )
            raise ImportError(msg)

        file_paths = [str(file.path) for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        pic_desc_config: dict | None = None
        if self.pic_desc_llm is not None:
            pic_desc_config = _serialize_pydantic_model(self.pic_desc_llm)

        args = {
            "file_paths": file_paths,
            "pipeline": self.pipeline,
            "ocr_engine": self.ocr_engine,
            "do_picture_classification": self.do_picture_classification,
            "pic_desc_config": pic_desc_config,
            "pic_desc_prompt": self.pic_desc_prompt,
        }

        # Use Popen with a polling loop (same pattern as Read File advanced mode).
        # This avoids multiprocessing/threading issues under Gunicorn and keeps the
        # SSE event stream alive via periodic heartbeat logs.
        docling_timeout = 600  # 10 minutes
        poll_interval = 5

        # Use a temporary file for stdout to avoid pipe buffer deadlocks.
        # Docling (and its transitive imports: PyTorch, transformers, etc.) can
        # write large amounts of output.  With subprocess.PIPE the OS pipe
        # buffer (~16 KB on macOS) fills up, the child blocks on write, and the
        # parent - which only reads *after* the child exits - waits forever.
        import tempfile

        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            proc = subprocess.Popen(  # noqa: S603
                [sys.executable, "-u", "-c", self._CHILD_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
            )
            proc.stdin.write(json.dumps(args).encode("utf-8"))
            proc.stdin.close()

            start = time.monotonic()
            while proc.poll() is None:
                elapsed = time.monotonic() - start
                if elapsed >= docling_timeout:
                    proc.kill()
                    proc.wait()
                    msg = (
                        f"Docling processing timed out after {docling_timeout}s. Try processing fewer or smaller files."
                    )
                    raise TimeoutError(msg)
                self.log(f"Docling processing in progress ({int(elapsed)}s elapsed)...")
                time.sleep(poll_interval)

            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_bytes = stdout_file.read()
            stderr_bytes = stderr_file.read()

        if not stdout_bytes:
            err_msg = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "no output"
            msg = f"Docling subprocess error: {err_msg}"
            raise RuntimeError(msg)

        try:
            payload = json.loads(stdout_bytes.decode("utf-8"))
        except Exception as e:
            err_msg = stderr_bytes.decode("utf-8", errors="replace")
            msg = f"Invalid JSON from Docling subprocess: {e}. stderr={err_msg}"
            raise RuntimeError(msg) from e

        if not payload.get("ok"):
            error_msg = payload.get("error", "Unknown Docling error")
            if "not installed" in error_msg.lower():
                raise ImportError(error_msg)
            raise RuntimeError(error_msg)

        # Reconstruct DoclingDocument objects from JSON dicts returned by the child
        from docling_core.types.doc import DoclingDocument

        raw_results = payload.get("results", [])
        processed_data: list[Data | None] = []
        for r in raw_results:
            if r is None:
                processed_data.append(None)
                continue
            try:
                doc = DoclingDocument.model_validate(r["document"])
            except Exception:  # noqa: BLE001
                # Fall back to keeping the raw dict if validation fails
                doc = r["document"]
            processed_data.append(Data(data={"doc": doc, "file_path": r["file_path"]}))

        return self.rollup_data(file_list, processed_data)
