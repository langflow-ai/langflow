from multiprocessing import Queue, get_context

from langflow.base.data import BaseFileComponent
from langflow.components.docling import docling_worker
from langflow.inputs import DropdownInput
from langflow.schema import Data


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
        *BaseFileComponent._base_inputs,
        DropdownInput(
            name="pipeline",
            display_name="Pipeline",
            info="Docling pipeline to use",
            options=["standard", "vlm"],
            real_time_refresh=False,
            value="standard",
        ),
        DropdownInput(
            name="ocr_engine",
            display_name="Ocr",
            info="OCR engine to use",
            options=["", "easyocr", "tesserocr", "rapidocr", "ocrmac"],
            real_time_refresh=False,
            value="",
        ),
        # TODO: expose more Docling options
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        file_paths = [file.path for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        ctx = get_context("spawn")
        queue: Queue = ctx.Queue()
        proc = ctx.Process(
            target=docling_worker,
            args=(file_paths, queue, self.pipeline, self.ocr_engine),
        )

        proc.start()
        result = queue.get()
        proc.join()

        # Check if there was an error in the worker
        if isinstance(result, dict) and "error" in result:
            raise ImportError(result["error"])

        processed_data = [Data(data={"doc": r["document"], "file_path": r["file_path"]}) if r else None for r in result]

        return self.rollup_data(file_list, processed_data)
