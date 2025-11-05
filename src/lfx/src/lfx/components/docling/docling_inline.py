import time
from multiprocessing import Queue, get_context
from queue import Empty

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

    def _wait_for_result_with_process_monitoring(self, queue: Queue, proc, timeout: int = 300):
        """Wait for result from queue while monitoring process health.

        Handles cases where process crashes without sending result.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if not proc.is_alive():
                # Process died, try to get any result it might have sent
                try:
                    result = queue.get_nowait()
                except Empty:
                    # Process died without sending result
                    msg = f"Worker process crashed unexpectedly without producing result. Exit code: {proc.exitcode}"
                    raise RuntimeError(msg) from None
                else:
                    self.log("Process completed and result retrieved")
                    return result

            # Poll the queue instead of blocking
            try:
                result = queue.get(timeout=1)
            except Empty:
                # No result yet, continue monitoring
                continue
            else:
                self.log("Result received from worker process")
                return result

        # Overall timeout reached
        msg = f"Process timed out after {timeout} seconds"
        raise TimeoutError(msg)

    def _terminate_process_gracefully(self, proc, timeout_terminate: int = 10, timeout_kill: int = 5):
        """Terminate process gracefully with escalating signals.

        First tries SIGTERM, then SIGKILL if needed.
        """
        if not proc.is_alive():
            return

        self.log("Attempting graceful process termination with SIGTERM")
        proc.terminate()  # Send SIGTERM
        proc.join(timeout=timeout_terminate)

        if proc.is_alive():
            self.log("Process didn't respond to SIGTERM, using SIGKILL")
            proc.kill()  # Send SIGKILL
            proc.join(timeout=timeout_kill)

            if proc.is_alive():
                self.log("Warning: Process still alive after SIGKILL")

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

        ctx = get_context("spawn")
        queue: Queue = ctx.Queue()
        proc = ctx.Process(
            target=docling_worker,
            kwargs={
                "file_paths": file_paths,
                "queue": queue,
                "pipeline": self.pipeline,
                "ocr_engine": self.ocr_engine,
                "do_picture_classification": self.do_picture_classification,
                "pic_desc_config": pic_desc_config,
                "pic_desc_prompt": self.pic_desc_prompt,
            },
        )

        result = None
        proc.start()

        try:
            result = self._wait_for_result_with_process_monitoring(queue, proc, timeout=300)
        except KeyboardInterrupt:
            self.log("Docling process cancelled by user")
            result = []
        except Exception as e:
            self.log(f"Error during processing: {e}")
            raise
        finally:
            # Improved cleanup with graceful termination
            try:
                self._terminate_process_gracefully(proc)
            finally:
                # Always close and cleanup queue resources
                try:
                    queue.close()
                    queue.join_thread()
                except Exception as e:  # noqa: BLE001
                    # Ignore cleanup errors, but log them
                    self.log(f"Warning: Error during queue cleanup - {e}")

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
