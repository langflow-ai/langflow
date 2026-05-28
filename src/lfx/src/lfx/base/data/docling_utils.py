import importlib
import signal
import traceback
from contextlib import suppress
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, SecretStr, TypeAdapter

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument
else:
    DoclingDocument = Any


class DoclingDependencyError(Exception):
    """Custom exception for missing Docling dependencies."""

    def __init__(self, dependency_name: str, install_command: str):
        self.dependency_name = dependency_name
        self.install_command = install_command
        super().__init__(f"{dependency_name} is not correctly installed. {install_command}")


@dataclass(slots=True)
class SerializedDoclingOrigin:
    """Small origin object compatible with the DoclingDocument metadata used by components."""

    filename: str | None = None
    binary_hash: str | int | None = None
    mimetype: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "SerializedDoclingOrigin | None":
        if value is None:
            return None
        if not isinstance(value, dict):
            return cls(
                filename=getattr(value, "filename", None),
                binary_hash=getattr(value, "binary_hash", None),
                mimetype=getattr(value, "mimetype", None),
            )
        return cls(
            filename=value.get("filename"),
            binary_hash=value.get("binary_hash"),
            mimetype=value.get("mimetype") or value.get("mime_type"),
        )


class SerializedDoclingDocument:
    """DoclingDocument-compatible wrapper for serialized Docling JSON.

    Docling Serve returns JSON content that is already enough for the export component
    to produce useful text formats. This wrapper keeps that path working when
    docling-core is not installed.
    """

    def __init__(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict):
            msg = f"Expected serialized DoclingDocument as dict, got {type(document).__name__}."
            raise TypeError(msg)
        self._document = document
        self.name = document.get("name")
        self.origin = SerializedDoclingOrigin.from_value(document.get("origin"))

    @classmethod
    def model_validate(cls, document: dict[str, Any]) -> "SerializedDoclingDocument":
        return cls(document)

    def export_to_dict(self) -> dict[str, Any]:
        return self._document

    def export_to_text(self, **_kwargs: Any) -> str:
        blocks = [block for block in self._text_blocks(include_tables=True) if block]
        return "\n\n".join(blocks)

    def export_to_markdown(
        self,
        *,
        image_placeholder: str = "<!-- image -->",
        page_break_placeholder: str = "",
        **_kwargs: Any,
    ) -> str:
        blocks: list[str] = []
        previous_page = None
        for kind, item in self._document_items():
            page_no = self._page_no(item)
            if previous_page is not None and page_no != previous_page and page_break_placeholder:
                blocks.append(page_break_placeholder)
            if page_no is not None:
                previous_page = page_no

            if kind == "texts":
                text = self._item_text(item)
                if text:
                    blocks.append(self._markdown_text_block(item, text))
            elif kind == "tables":
                table = self._table_text(item, markdown=True)
                if table:
                    blocks.append(table)
            elif kind == "pictures" and image_placeholder:
                blocks.append(image_placeholder)

        return "\n\n".join(block for block in blocks if block)

    def export_to_html(self, **_kwargs: Any) -> str:
        blocks: list[str] = []
        for kind, item in self._document_items():
            if kind == "texts":
                text = self._item_text(item)
                if not text:
                    continue
                label = str(item.get("label") or "").lower()
                if label in {"title", "section_header", "heading", "header"}:
                    level = self._heading_level(item)
                    blocks.append(f"<h{level}>{escape(text)}</h{level}>")
                elif "list" in label:
                    blocks.append(f"<ul><li>{escape(text)}</li></ul>")
                else:
                    blocks.append(f"<p>{escape(text)}</p>")
            elif kind == "tables":
                table = self._table_text(item, markdown=False)
                if table:
                    rows = []
                    for row in table.splitlines():
                        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row.split("\t"))
                        rows.append(f"<tr>{cells}</tr>")
                    blocks.append(f"<table>{''.join(rows)}</table>")
        return "\n".join(blocks)

    def export_to_doctags(self, **_kwargs: Any) -> str:
        tags = []
        for kind, item in self._document_items():
            if kind == "texts":
                text = self._item_text(item)
                if text:
                    label = escape(str(item.get("label") or "text"))
                    tags.append(f'<text label="{label}">{escape(text)}</text>')
            elif kind == "tables":
                table = self._table_text(item, markdown=False)
                if table:
                    tags.append(f"<table>{escape(table)}</table>")
        return "<document>" + "".join(tags) + "</document>"

    def _document_items(self) -> list[tuple[str, dict[str, Any]]]:
        ordered_items: list[tuple[str, dict[str, Any]]] = []
        body = self._document.get("body")
        children = body.get("children") if isinstance(body, dict) else None
        if isinstance(children, list):
            for child in children:
                item = self._resolve_child(child)
                if item is not None:
                    ordered_items.append(item)

        if ordered_items:
            return ordered_items

        for kind in ("texts", "tables", "pictures"):
            values = self._document.get(kind)
            if isinstance(values, list):
                ordered_items.extend((kind, value) for value in values if isinstance(value, dict))
        return ordered_items

    def _resolve_child(self, child: Any) -> tuple[str, dict[str, Any]] | None:
        if not isinstance(child, dict):
            return None
        ref = child.get("$ref") or child.get("ref")
        if not isinstance(ref, str):
            return None
        kind, separator, index = ref.removeprefix("#/").partition("/")
        if not separator:
            return None
        values = self._document.get(kind)
        if kind not in {"texts", "tables", "pictures"} or not isinstance(values, list):
            return None
        try:
            value = values[int(index)]
        except (IndexError, TypeError, ValueError):
            return None
        if not isinstance(value, dict):
            return None
        return kind, value

    def _text_blocks(self, *, include_tables: bool) -> list[str]:
        blocks: list[str] = []
        for kind, item in self._document_items():
            if kind == "texts":
                text = self._item_text(item)
                if text:
                    blocks.append(text)
            elif include_tables and kind == "tables":
                table = self._table_text(item, markdown=False)
                if table:
                    blocks.append(table)
        return blocks

    @staticmethod
    def _item_text(item: dict[str, Any]) -> str:
        text = item.get("text")
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _page_no(item: dict[str, Any]) -> Any:
        prov = item.get("prov")
        if isinstance(prov, list) and prov and isinstance(prov[0], dict):
            return prov[0].get("page_no")
        return None

    @staticmethod
    def _heading_level(item: dict[str, Any]) -> int:
        try:
            level = int(item.get("level") or 1)
        except (TypeError, ValueError):
            level = 1
        return max(1, min(level, 6))

    def _markdown_text_block(self, item: dict[str, Any], text: str) -> str:
        label = str(item.get("label") or "").lower()
        if label in {"title", "section_header", "heading", "header"}:
            return f"{'#' * self._heading_level(item)} {text}"
        if "list" in label:
            return f"- {text}"
        if label in {"code", "formula"}:
            return f"```\n{text}\n```"
        return text

    @staticmethod
    def _table_text(item: dict[str, Any], *, markdown: bool) -> str:
        table_data = item.get("data") if isinstance(item.get("data"), dict) else item
        cells = table_data.get("table_cells") if isinstance(table_data, dict) else None
        if not isinstance(cells, list):
            return ""

        rows: dict[int, dict[int, str]] = {}
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            text = cell.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            row = cell.get("start_row_offset_idx", cell.get("row", 0))
            col = cell.get("start_col_offset_idx", cell.get("col", 0))
            try:
                row_index = int(row)
                col_index = int(col)
            except (TypeError, ValueError):
                continue
            rows.setdefault(row_index, {})[col_index] = text.strip()

        if not rows:
            return ""

        ordered_rows = []
        for row_index in sorted(rows):
            row = rows[row_index]
            ordered_rows.append([row.get(col_index, "") for col_index in range(max(row) + 1)])

        if not markdown:
            return "\n".join("\t".join(row) for row in ordered_rows)

        markdown_rows = ["| " + " | ".join(row) + " |" for row in ordered_rows]
        if len(markdown_rows) > 1:
            column_count = len(ordered_rows[0])
            markdown_rows.insert(1, "| " + " | ".join("---" for _ in range(column_count)) + " |")
        return "\n".join(markdown_rows)


def _get_docling_document_class():
    try:
        docling_doc_module = importlib.import_module("docling_core.types.doc")
    except ImportError as e:
        dependency_name = "docling-core"
        install_command = "Install Docling with `uv pip install 'langflow[docling]'`."
        raise DoclingDependencyError(dependency_name, install_command) from e
    return docling_doc_module.DoclingDocument


def get_docling_image_ref_mode(image_mode: str) -> Any:
    try:
        docling_doc_module = importlib.import_module("docling_core.types.doc")
    except ImportError:
        return image_mode
    return docling_doc_module.ImageRefMode(image_mode)


def coerce_docling_document(doc: Any) -> Any:
    if all(hasattr(doc, method) for method in ("export_to_markdown", "export_to_html", "export_to_text")):
        return doc
    if isinstance(doc, dict):
        if not _looks_like_serialized_docling_document(doc):
            msg = f"Expected serialized DoclingDocument fields, got keys: {sorted(doc.keys())}."
            raise TypeError(msg)
        try:
            docling_document = _get_docling_document_class()
        except DoclingDependencyError:
            return SerializedDoclingDocument.model_validate(doc)
        try:
            return docling_document.model_validate(doc)
        except (TypeError, ValueError):
            return SerializedDoclingDocument.model_validate(doc)
    if _is_docling_document(doc):
        return doc

    msg = f"Expected a DoclingDocument or serialized DoclingDocument, got {type(doc).__name__}."
    raise TypeError(msg)


def _looks_like_serialized_docling_document(value: Any) -> bool:
    docling_keys = ("texts", "tables", "pictures", "body", "origin", "name")
    return isinstance(value, dict) and any(key in value for key in docling_keys)


def _is_docling_document(value: Any) -> bool:
    if isinstance(value, SerializedDoclingDocument):
        return True
    if _looks_like_serialized_docling_document(value):
        return True
    try:
        docling_document = _get_docling_document_class()
    except DoclingDependencyError:
        return all(hasattr(value, method) for method in ("export_to_markdown", "export_to_html", "export_to_text"))
    return isinstance(value, docling_document)


def extract_docling_documents(
    data_inputs: Data | list[Data] | DataFrame, doc_key: str
) -> tuple[list[DoclingDocument], str | None]:
    """Extract DoclingDocument objects from data inputs.

    Args:
        data_inputs: The data inputs containing DoclingDocument objects
        doc_key: The key/column name to look for DoclingDocument objects

    Returns:
        A tuple of (documents, warning_message) where warning_message is None if no warning

    Raises:
        TypeError: If the data cannot be extracted or is invalid
    """
    documents: list[DoclingDocument] = []
    warning_message: str | None = None

    if isinstance(data_inputs, DataFrame):
        if not len(data_inputs):
            msg = "DataFrame is empty"
            raise TypeError(msg)

        # Primary: Check for exact column name match
        if doc_key in data_inputs.columns:
            try:
                documents = data_inputs[doc_key].tolist()
            except Exception as e:
                msg = f"Error extracting DoclingDocument from DataFrame column '{doc_key}': {e}"
                raise TypeError(msg) from e
        else:
            # Fallback: Search all columns for DoclingDocument objects
            found_column = None
            for col in data_inputs.columns:
                try:
                    # Check if this column contains DoclingDocument objects
                    sample = data_inputs[col].dropna().iloc[0] if len(data_inputs[col].dropna()) > 0 else None
                    if sample is not None and _is_docling_document(sample):
                        found_column = col
                        break
                except (IndexError, AttributeError):
                    continue

            if found_column:
                warning_message = (
                    f"Column '{doc_key}' not found, but found DoclingDocument objects in column '{found_column}'. "
                    f"Using '{found_column}' instead. Consider updating the 'Doc Key' parameter."
                )
                logger.warning(warning_message)
                try:
                    documents = data_inputs[found_column].tolist()
                except Exception as e:
                    msg = f"Error extracting DoclingDocument from DataFrame column '{found_column}': {e}"
                    raise TypeError(msg) from e
            else:
                # Provide helpful error message
                available_columns = list(data_inputs.columns)
                msg = (
                    f"Column '{doc_key}' not found in DataFrame. "
                    f"Available columns: {available_columns}. "
                    f"\n\nPossible solutions:\n"
                    f"1. Use the 'Data' output from Docling component instead of 'DataFrame' output\n"
                    f"2. Update the 'Doc Key' parameter to match one of the available columns\n"
                    f"3. If using VLM pipeline, try using the standard pipeline"
                )
                raise TypeError(msg)
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
                    if (
                        isinstance(input_, Data)
                        and doc_key in input_.data
                        and _is_docling_document(input_.data[doc_key])
                    )
                ]
                if not documents:
                    msg = f"No valid Data inputs found in {type(data_inputs)}"
                    raise TypeError(msg)
            except AttributeError as e:
                msg = f"Invalid input type in collection: {e}"
                raise TypeError(msg) from e
    return documents, warning_message


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


# Global cache for DocumentConverter instances
# This cache persists across multiple runs and thread invocations
@lru_cache(maxsize=4)
def _get_cached_converter(
    pipeline: str,
    ocr_engine: str,
    *,
    do_picture_classification: bool,
    pic_desc_config_hash: str | None,
):
    """Create and cache a DocumentConverter instance based on configuration.

    This function uses LRU caching to maintain DocumentConverter instances in memory,
    eliminating the 15-20 minute model loading time on subsequent runs.

    Args:
        pipeline: The pipeline type ("standard" or "vlm")
        ocr_engine: The OCR engine to use
        do_picture_classification: Whether to enable picture classification
        pic_desc_config_hash: Hash of the picture description config (for cache key)

    Returns:
        A cached or newly created DocumentConverter instance
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import OcrOptions, PdfPipelineOptions, VlmPipelineOptions
    from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
    from docling.models.factories import get_ocr_factory
    from docling.pipeline.vlm_pipeline import VlmPipeline

    logger.info(f"Creating DocumentConverter for pipeline={pipeline}, ocr_engine={ocr_engine}")

    # Configure the standard PDF pipeline
    def _get_standard_opts() -> PdfPipelineOptions:
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

        # Note: pic_desc_config_hash is for cache key only
        # Actual picture description is handled separately (non-cached path)
        _ = pic_desc_config_hash  # Mark as intentionally unused

        return pipeline_options

    # Configure the VLM pipeline
    def _get_vlm_opts() -> VlmPipelineOptions:
        return VlmPipelineOptions()

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


class _ShutdownRequestedError(Exception):
    """Raised by check_shutdown() to unwind the docling_worker call stack."""


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
    """Worker function for processing files with Docling using threading.

    This function now uses a globally cached DocumentConverter instance,
    significantly reducing processing time on subsequent runs from 15-20 minutes
    to just seconds.
    """
    # Signal handling for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum: int, frame) -> None:  # noqa: ARG001
        """Handle shutdown signals gracefully."""
        nonlocal shutdown_requested
        signal_names: dict[int, str] = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}
        signal_name = signal_names.get(signum, f"signal {signum}")

        logger.debug(f"Docling worker received {signal_name}, initiating graceful shutdown...")
        shutdown_requested = True

        # Send shutdown notification to parent thread
        with suppress(Exception):
            queue.put({"error": f"Worker interrupted by {signal_name}", "shutdown": True})

        # NOTE: Do NOT call sys.exit() here. This function runs in a thread
        # (not a subprocess), so sys.exit() would raise SystemExit which can
        # crash the host process in single-worker setups. Instead, just set
        # the flag and let check_shutdown() terminate the worker loop.

    def check_shutdown() -> None:
        """Check if shutdown was requested and raise to unwind if so."""
        if shutdown_requested:
            logger.info("Shutdown requested, exiting worker...")

            with suppress(Exception):
                queue.put({"error": "Worker shutdown requested", "shutdown": True})

            raise _ShutdownRequestedError

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
        from docling.datamodel.base_models import ConversionStatus, InputFormat  # noqa: F401
        from docling.datamodel.pipeline_options import OcrOptions, PdfPipelineOptions, VlmPipelineOptions  # noqa: F401
        from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption  # noqa: F401
        from docling.models.factories import get_ocr_factory  # noqa: F401
        from docling.pipeline.vlm_pipeline import VlmPipeline  # noqa: F401
        from langchain_docling.picture_description import PictureDescriptionLangChainOptions  # noqa: F401

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

    # Use cached converter instead of creating new one each time
    # This is the key optimization that eliminates 15-20 minute model load times
    def _get_converter() -> DocumentConverter:
        check_shutdown()  # Check before heavy operations

        # For now, we don't support pic_desc_config caching due to serialization complexity
        # This is a known limitation that can be addressed in a future enhancement
        if pic_desc_config:
            logger.warning(
                "Picture description with LLM is not yet supported with cached converters. "
                "Using non-cached converter for this request."
            )
            # Fall back to creating a new converter (old behavior)
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
            from docling.models.factories import get_ocr_factory
            from langchain_docling.picture_description import PictureDescriptionLangChainOptions

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = ocr_engine not in {"", "None"}
            if pipeline_options.do_ocr:
                ocr_factory = get_ocr_factory(allow_external_plugins=False)
                ocr_options = ocr_factory.create_options(kind=ocr_engine)
                pipeline_options.ocr_options = ocr_options

            pipeline_options.do_picture_classification = do_picture_classification
            pic_desc_llm = _deserialize_pydantic_model(pic_desc_config)
            logger.info("Docling enabling the picture description stage.")
            pipeline_options.do_picture_description = True
            pipeline_options.allow_external_plugins = True
            pipeline_options.picture_description_options = PictureDescriptionLangChainOptions(
                llm=pic_desc_llm,
                prompt=pic_desc_prompt,
            )

            pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)
            format_options: dict[InputFormat, FormatOption] = {
                InputFormat.PDF: pdf_format_option,
                InputFormat.IMAGE: pdf_format_option,
            }
            return DocumentConverter(format_options=format_options)

        # Use cached converter - this is where the magic happens!
        # First run: creates and caches converter (15-20 min)
        # Subsequent runs: reuses cached converter (seconds)
        pic_desc_config_hash = None  # Will be None since we checked above
        return _get_cached_converter(
            pipeline=pipeline,
            ocr_engine=ocr_engine,
            do_picture_classification=do_picture_classification,
            pic_desc_config_hash=pic_desc_config_hash,
        )

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

    except _ShutdownRequestedError:
        logger.info("Docling worker stopped by shutdown request")
        return
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
