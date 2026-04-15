import queue
import threading
import time

from lfx.base.data import BaseFileComponent
from lfx.base.data.docling_utils import _serialize_pydantic_model, docling_worker
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

    def _wait_for_result_with_thread_monitoring(
        self, result_queue: queue.Queue, thread: threading.Thread, timeout: int = 300
    ):
        """Wait for result from queue while monitoring thread health.

        Handles cases where thread crashes without sending result.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if thread is still alive
            if not thread.is_alive():
                # Thread finished, try to get any result it might have sent
                try:
                    result = result_queue.get_nowait()
                except queue.Empty:
                    # Thread finished without sending result
                    msg = "Worker thread crashed unexpectedly without producing result."
                    raise RuntimeError(msg) from None
                else:
                    self.log("Thread completed and result retrieved")
                    return result

            # Poll the queue instead of blocking
            try:
                result = result_queue.get(timeout=1)
            except queue.Empty:
                # No result yet, continue monitoring
                continue
            else:
                self.log("Result received from worker thread")
                return result

        # Overall timeout reached
        msg = f"Thread timed out after {timeout} seconds"
        raise TimeoutError(msg)

    def _stop_thread_gracefully(self, thread: threading.Thread, timeout: int = 10):
        """Wait for thread to complete gracefully.

        Note: Python threads cannot be forcefully killed, so we just wait.
        The thread should respond to shutdown signals via the queue.
        """
        if not thread.is_alive():
            return

        self.log("Waiting for thread to complete gracefully")
        thread.join(timeout=timeout)

        if thread.is_alive():
            self.log("Warning: Thread still alive after timeout")

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
        except ImportError as e:
            msg = (
                "Docling is an optional dependency. Install with `uv pip install 'langflow[docling]'` or refer to the "
                "documentation on how to install optional dependencies."
            )
            raise ImportError(msg) from e

        file_paths = [file.path for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        pic_desc_config: dict | None = None
        if self.pic_desc_llm is not None:
            pic_desc_config = _serialize_pydantic_model(self.pic_desc_llm)

        # Use threading instead of multiprocessing for memory sharing
        # This enables the global DocumentConverter cache to work across runs
        result_queue: queue.Queue = queue.Queue()
        thread = threading.Thread(
            target=docling_worker,
            kwargs={
                "file_paths": file_paths,
                "queue": result_queue,
                "pipeline": self.pipeline,
                "ocr_engine": self.ocr_engine,
                "do_picture_classification": self.do_picture_classification,
                "pic_desc_config": pic_desc_config,
                "pic_desc_prompt": self.pic_desc_prompt,
            },
            daemon=False,  # Allow thread to complete even if main thread exits
        )

        result = None
        thread.start()

        try:
            result = self._wait_for_result_with_thread_monitoring(result_queue, thread, timeout=300)
        except KeyboardInterrupt:
            self.log("Docling thread cancelled by user")
            result = []
        except Exception as e:
            self.log(f"Error during processing: {e}")
            raise
        finally:
            # Wait for thread to complete gracefully
            self._stop_thread_gracefully(thread)

        # Enhanced error checking with dependency-specific handling
        if isinstance(result, dict) and "error" in result:
            error_msg = result["error"]

            # Handle dependency errors specifically
            if result.get("error_type") == "dependency_error":
                dependency_name = result.get("dependency_name", "Unknown dependency")
                install_command = result.get("install_command", "Please check documentation")

                # Create a user-friendly error message
                user_message = (
                    f"Missing OCR dependency: {dependency_name}. "
                    f"{install_command} "
                    f"Alternatively, you can set OCR Engine to 'None' to disable OCR processing."
                )
                raise ImportError(user_message)

            # Handle other specific errors
            if error_msg.startswith("Docling is not installed"):
                raise ImportError(error_msg)

            # Handle graceful shutdown
            if "Worker interrupted by SIGINT" in error_msg or "shutdown" in result:
                self.log("Docling process cancelled by user")
                result = []
            else:
                raise RuntimeError(error_msg)

        processed_data = [Data(data={"doc": r["document"], "file_path": r["file_path"]}) if r else None for r in result]
        return self.rollup_data(file_list, processed_data)
