import importlib
import signal
import sys
import traceback
from contextlib import suppress
from typing import TYPE_CHECKING

from docling_core.types.doc import DoclingDocument
from pydantic import BaseModel, SecretStr, TypeAdapter

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class DoclingDependencyError(Exception):
    """Custom exception for missing Docling dependencies."""

    def __init__(self, dependency_name: str, install_command: str):
        self.dependency_name = dependency_name
        self.install_command = install_command
        super().__init__(f"{dependency_name} is not correctly installed. {install_command}")


def extract_docling_documents(data_inputs: Data | list[Data] | DataFrame, doc_key: str) -> list[DoclingDocument]:
    documents: list[DoclingDocument] = []
    if isinstance(data_inputs, DataFrame):
        if not len(data_inputs):
            msg = "DataFrame is empty"
            raise TypeError(msg)

        if doc_key not in data_inputs.columns:
            msg = f"Column '{doc_key}' not found in DataFrame"
            raise TypeError(msg)
        try:
            documents = data_inputs[doc_key].tolist()
        except Exception as e:
            msg = f"Error extracting DoclingDocument from DataFrame: {e}"
            raise TypeError(msg) from e
    else:
        if not data_inputs:
            msg = "No data inputs provided"
            raise TypeError(msg)

        if isinstance(data_inputs, Data):
            if doc_key not in data_inputs.data:
                msg = (
                    f"'{doc_key}' field not available in the input Data. "
                    "Check that your input is a DoclingDocument. "
                    "You can use the Docling component to convert your input to a DoclingDocument."
                )
                raise TypeError(msg)
            documents = [data_inputs.data[doc_key]]
        else:
            try:
                documents = [
                    input_.data[doc_key]
                    for input_ in data_inputs
                    if isinstance(input_, Data)
                    and doc_key in input_.data
                    and isinstance(input_.data[doc_key], DoclingDocument)
                ]
                if not documents:
                    msg = f"No valid Data inputs found in {type(data_inputs)}"
                    raise TypeError(msg)
            except AttributeError as e:
                msg = f"Invalid input type in collection: {e}"
                raise TypeError(msg) from e
    return documents


def _unwrap_secrets(obj):
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, dict):
        return {k: _unwrap_secrets(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unwrap_secrets(v) for v in obj]
    return obj


def _dump_with_secrets(model: BaseModel):
    return _unwrap_secrets(model.model_dump(mode="python", round_trip=True))


def _serialize_pydantic_model(model: BaseModel):
    return {
        "__class_path__": f"{model.__class__.__module__}.{model.__class__.__name__}",
        "config": _dump_with_secrets(model),
    }


def _deserialize_pydantic_model(data: dict):
    module_name, class_name = data["__class_path__"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    adapter = TypeAdapter(cls)
    return adapter.validate_python(data["config"])


def docling_worker(
    *,
    file_paths: list[str],
    queue,
    pipeline: str,
    ocr_engine: str,
    do_picture_classification: bool,
    pic_desc_config: dict | None,
    pic_desc_prompt: str,
):
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
        from docling.datamodel.pipeline_options import OcrOptions, PdfPipelineOptions, VlmPipelineOptions
        from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
        from docling.models.factories import get_ocr_factory
        from docling.pipeline.vlm_pipeline import VlmPipeline
        from langchain_docling.picture_description import PictureDescriptionLangChainOptions

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
        pipeline_options.do_ocr = ocr_engine not in {"", "None"}
        if pipeline_options.do_ocr:
            ocr_factory = get_ocr_factory(
                allow_external_plugins=False,
            )

            ocr_options: OcrOptions = ocr_factory.create_options(
                kind=ocr_engine,
            )
            pipeline_options.ocr_options = ocr_options

        pipeline_options.do_picture_classification = do_picture_classification

        if pic_desc_config:
            pic_desc_llm: BaseChatModel = _deserialize_pydantic_model(pic_desc_config)

            logger.info("Docling enabling the picture description stage.")
            pipeline_options.do_picture_description = True
            pipeline_options.allow_external_plugins = True
            pipeline_options.picture_description_options = PictureDescriptionLangChainOptions(
                llm=pic_desc_llm,
                prompt=pic_desc_prompt,
            )
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
                single_result = converter.convert_all([file_path])
                results.extend(single_result)
                check_shutdown()

            except ImportError as import_error:
                # Simply pass ImportError to main process for handling
                queue.put(
                    {"error": str(import_error), "error_type": "import_error", "original_exception": "ImportError"}
                )
                return

            except (OSError, ValueError, RuntimeError) as file_error:
                error_msg = str(file_error)

                # Check for specific dependency errors and identify the dependency name
                dependency_name = None
                if "ocrmac is not correctly installed" in error_msg:
                    dependency_name = "ocrmac"
                elif "easyocr" in error_msg and "not installed" in error_msg:
                    dependency_name = "easyocr"
                elif "tesserocr" in error_msg and "not installed" in error_msg:
                    dependency_name = "tesserocr"
                elif "rapidocr" in error_msg and "not installed" in error_msg:
                    dependency_name = "rapidocr"

                if dependency_name:
                    queue.put(
                        {
                            "error": error_msg,
                            "error_type": "dependency_error",
                            "dependency_name": dependency_name,
                            "original_exception": type(file_error).__name__,
                        }
                    )
                    return

                # If not a dependency error, log and continue with other files
                logger.error(f"Error processing file {file_path}: {file_error}")
                check_shutdown()

            except Exception as file_error:  # noqa: BLE001
                logger.error(f"Unexpected error processing file {file_path}: {file_error}")
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
