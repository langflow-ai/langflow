from __future__ import annotations

import signal
import sys
import traceback
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from loguru import logger

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
    # Signal handling for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum: int, frame) -> None:  # noqa: ARG001
        """Handle shutdown signals gracefully."""
        nonlocal shutdown_requested
        signal_names: dict[int, str] = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}
        signal_name = signal_names.get(signum, f"signal {signum}")

        logger.debug(f"Docling worker received {signal_name}, initiating graceful shutdown...")
        shutdown_requested = True

        # Send shutdown notification to parent process
        with suppress(Exception):
            queue.put({"error": f"Worker interrupted by {signal_name}", "shutdown": True})

        # Exit gracefully
        sys.exit(0)

    def check_shutdown() -> None:
        """Check if shutdown was requested and exit if so."""
        if shutdown_requested:
            logger.info("Shutdown requested, exiting worker...")

            with suppress(Exception):
                queue.put({"error": "Worker shutdown requested", "shutdown": True})

            sys.exit(0)

    # Register signal handlers early
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.debug("Signal handlers registered for graceful shutdown")
    except (OSError, ValueError) as e:
        # Some signals might not be available on all platforms
        logger.warning(f"Warning: Could not register signal handlers: {e}")

    # Check for shutdown before heavy imports
    check_shutdown()

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

        # Check for shutdown after imports
        check_shutdown()
        logger.debug("Docling dependencies loaded successfully")

    except ModuleNotFoundError:
        msg = (
            "Docling is an optional dependency of Langflow. "
            "Install with `uv pip install 'langflow[docling]'` "
            "or refer to the documentation"
        )
        queue.put({"error": msg})
        return
    except ImportError as e:
        # A different import failed (e.g., a transitive dependency); preserve details.
        queue.put({"error": f"Failed to import a Docling dependency: {e}"})
        return
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt during imports, exiting...")
        queue.put({"error": "Worker interrupted during imports", "shutdown": True})
        return

    # Configure the standard PDF pipeline
    def _get_standard_opts() -> PdfPipelineOptions:
        check_shutdown()  # Check before heavy operations

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
        check_shutdown()  # Check before heavy operations
        return VlmPipelineOptions()

    # Configure the main format options and create the DocumentConverter()
    def _get_converter() -> DocumentConverter:
        check_shutdown()  # Check before heavy operations

        if pipeline == "standard":
            pdf_format_option = PdfFormatOption(
                pipeline_options=_get_standard_opts(),
            )
        elif pipeline == "vlm":
            pdf_format_option = PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=_get_vlm_opts())
        else:
            msg = f"Unknown pipeline: {pipeline!r}"
            raise ValueError(msg)

        format_options: dict[InputFormat, FormatOption] = {
            InputFormat.PDF: pdf_format_option,
            InputFormat.IMAGE: pdf_format_option,
        }

        return DocumentConverter(format_options=format_options)

    try:
        # Check for shutdown before creating converter (can be slow)
        check_shutdown()
        logger.info(f"Initializing {pipeline} pipeline with OCR: {ocr_engine or 'disabled'}")

        converter = _get_converter()

        # Check for shutdown before processing files
        check_shutdown()
        logger.info(f"Starting to process {len(file_paths)} files...")

        # Process files with periodic shutdown checks
        results = []
        for i, file_path in enumerate(file_paths):
            # Check for shutdown before processing each file
            check_shutdown()

            logger.debug(f"Processing file {i + 1}/{len(file_paths)}: {file_path}")

            try:
                # Process single file (we can't easily interrupt convert_all)
                single_result = converter.convert_all([file_path])
                results.extend(single_result)

                # Check for shutdown after each file
                check_shutdown()

            except (OSError, ValueError, RuntimeError, ImportError) as file_error:
                # Handle specific file processing errors
                logger.error(f"Error processing file {file_path}: {file_error}")
                # Continue with other files, but check for shutdown
                check_shutdown()
            except Exception as file_error:  # noqa: BLE001
                # Catch any other unexpected errors to prevent worker crash
                logger.error(f"Unexpected error processing file {file_path}: {file_error}")
                # Continue with other files, but check for shutdown
                check_shutdown()

        # Final shutdown check before sending results
        check_shutdown()

        # Process the results while maintaining the original structure
        processed_data = [
            {"document": res.document, "file_path": str(res.input.file), "status": res.status.name}
            if res.status == ConversionStatus.SUCCESS
            else None
            for res in results
        ]

        logger.info(f"Successfully processed {len([d for d in processed_data if d])} files")
        queue.put(processed_data)

    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt during processing, exiting gracefully...")
        queue.put({"error": "Worker interrupted during processing", "shutdown": True})
        return
    except Exception as e:  # noqa: BLE001
        if shutdown_requested:
            logger.exception("Exception occurred during shutdown, exiting...")
            return

        # Send any processing error to the main process with traceback
        error_info = {"error": str(e), "traceback": traceback.format_exc()}
        logger.error(f"Error in worker: {error_info}")
        queue.put(error_info)
    finally:
        logger.info("Docling worker finishing...")
        # Ensure we don't leave any hanging processes
        if shutdown_requested:
            logger.debug("Worker shutdown completed")
        else:
            logger.debug("Worker completed normally")
