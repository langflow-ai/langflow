from langflow.base.data import BaseFileComponent
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
        try:
            from docling.datamodel.base_models import ConversionStatus, InputFormat
            from docling.datamodel.pipeline_options import (
                OcrOptions,
                PdfPipelineOptions,
                VlmPipelineOptions,
            )
            from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
            from docling.models.factories import get_ocr_factory
            from docling.pipeline.vlm_pipeline import VlmPipeline
        except ImportError as e:
            msg = (
                "Docling is an optional dependency. Install with `uv pip install 'langflow[docling]'` or refer to the "
                "documentation on how to install optional dependencies."
            )
            raise ImportError(msg) from e

        # Configure the standard PDF pipeline
        def _get_standard_opts() -> PdfPipelineOptions:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = self.ocr_engine != ""
            if pipeline_options.do_ocr:
                ocr_factory = get_ocr_factory(
                    allow_external_plugins=False,
                )

                ocr_options: OcrOptions = ocr_factory.create_options(
                    kind=self.ocr_engine,
                )
                pipeline_options.ocr_options = ocr_options
            return pipeline_options

        # Configure the VLM pipeline
        def _get_vlm_opts() -> VlmPipelineOptions:
            return VlmPipelineOptions()

        # Configure the main format options and create the DocumentConverter()
        def _get_converter() -> DocumentConverter:
            if self.pipeline == "standard":
                pdf_format_option = PdfFormatOption(
                    pipeline_options=_get_standard_opts(),
                )
            elif self.pipeline == "vlm":
                pdf_format_option = PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=_get_vlm_opts())

            format_options: dict[InputFormat, FormatOption] = {
                InputFormat.PDF: pdf_format_option,
                InputFormat.IMAGE: pdf_format_option,
            }

            return DocumentConverter(format_options=format_options)

        file_paths = [file.path for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        converter = _get_converter()
        results = converter.convert_all(file_paths)

        processed_data: list[Data | None] = [
            Data(data={"doc": res.document, "file_path": str(res.input.file)})
            if res.status == ConversionStatus.SUCCESS
            else None
            for res in results
        ]

        return self.rollup_data(file_list, processed_data)
