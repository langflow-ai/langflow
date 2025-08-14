from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .chunk_docling_document import ChunkDoclingDocumentComponent
    from .docling_inline import DoclingInlineComponent
    from .docling_remote import DoclingRemoteComponent
    from .export_docling_document import ExportDoclingDocumentComponent

_dynamic_imports = {
    "ChunkDoclingDocumentComponent": "chunk_docling_document",
    "DoclingInlineComponent": "docling_inline",
    "DoclingRemoteComponent": "docling_remote",
    "ExportDoclingDocumentComponent": "export_docling_document",
}

__all__ = [
    "ChunkDoclingDocumentComponent",
    "DoclingInlineComponent",
    "DoclingRemoteComponent",
    "ExportDoclingDocumentComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import docling components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)


def docling_worker(file_paths: list[str], queue, pipeline: str, ocr_engine: str):
    """Worker function for processing files with Docling in a separate process."""
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
    except ImportError:
        msg = (
            "Docling is not installed. Please install it with `uv pip install docling` or"
            " `uv pip install langflow[docling]`."
        )
        # Send error to the main process
        queue.put({"error": msg})
        return

    # Configure the standard PDF pipeline
    def _get_standard_opts() -> PdfPipelineOptions:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = ocr_engine != ""
        if pipeline_options.do_ocr:
            ocr_factory = get_ocr_factory(
                allow_external_plugins=False,
            )

            ocr_options: OcrOptions = ocr_factory.create_options(
                kind=ocr_engine,
            )
            pipeline_options.ocr_options = ocr_options
        return pipeline_options

    # Configure the VLM pipeline
    def _get_vlm_opts() -> VlmPipelineOptions:
        return VlmPipelineOptions()

    # Configure the main format options and create the DocumentConverter()
    def _get_converter() -> DocumentConverter:
        if pipeline == "standard":
            pdf_format_option = PdfFormatOption(
                pipeline_options=_get_standard_opts(),
            )
        elif pipeline == "vlm":
            pdf_format_option = PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=_get_vlm_opts())

        format_options: dict[InputFormat, FormatOption] = {
            InputFormat.PDF: pdf_format_option,
            InputFormat.IMAGE: pdf_format_option,
        }

        return DocumentConverter(format_options=format_options)

    try:
        converter = _get_converter()
        results = converter.convert_all(file_paths)

        # Process the results while maintaining the original structure
        processed_data = [
            {"document": res.document, "file_path": str(res.input.file), "status": res.status.name}
            if res.status == ConversionStatus.SUCCESS
            else None
            for res in results
        ]

        queue.put(processed_data)

    except Exception as e:  # noqa: BLE001
        # Send any processing error to the main process
        queue.put({"error": str(e)})
