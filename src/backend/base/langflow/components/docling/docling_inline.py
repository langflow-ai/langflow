import time
from multiprocessing import Queue, get_context
from queue import Empty

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

        # Check if there was an error in the worker
        if isinstance(result, dict) and "error" in result:
            msg = result["error"]
            if msg.startswith("Docling is not installed"):
                raise ImportError(msg)
            # Handle interrupt gracefully - return empty result instead of raising error
            if "Worker interrupted by SIGINT" in msg or "shutdown" in result:
                self.log("Docling process cancelled by user")
                result = []
            else:
                raise RuntimeError(msg)

        processed_data = [Data(data={"doc": r["document"], "file_path": r["file_path"]}) if r else None for r in result]
        return self.rollup_data(file_list, processed_data)
