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
        "png",
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
        from docling.datamodel.base_models import ConversionStatus, InputFormat
        from docling.datamodel.pipeline_options import (
            OcrOptions,
            PdfPipelineOptions,
            VlmPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
        from docling.models.factories import get_ocr_factory
        from docling.pipeline.vlm_pipeline import VlmPipeline

        def _get_converter() -> DocumentConverter:
            pipeline_options: PdfPipelineOptions | VlmPipelineOptions
            if self.pipeline == "standard":
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

                pdf_format_option = PdfFormatOption(
                    pipeline_options=pipeline_options,
                )

            elif self.pipeline == "vlm":
                pipeline_options = VlmPipelineOptions()
                pdf_format_option = PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=pipeline_options)

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
