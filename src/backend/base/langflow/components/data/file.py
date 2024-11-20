from pathlib import Path

from langflow.base.data import BaseFileComponent
from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.io import BoolInput, IntInput
from langflow.schema import Data


class FileComponent(BaseFileComponent):
    """Handles loading and processing of individual or zipped text files.

    This component supports processing multiple valid files within a zip archive,
    resolving paths, validating file types, and optionally using multithreading for processing.
    """

    display_name = "File"
    description = "Load a file to be used in your project."
    icon = "file-text"
    name = "File"

    VALID_EXTENSIONS = TEXT_FILE_TYPES

    inputs = [
        *BaseFileComponent._base_inputs,
        BoolInput(
            name="use_multithreading",
            display_name="[Deprecated] Use Multithreading",
            advanced=True,
            value=True,
            info="Set 'Processing Concurrency' greater than 1 to enable multithreading.",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=False,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[Path]) -> list[Data]:
        """Processes a list of individual files and returns parsed data.

        This method supports optional multithreading for improved performance
        when processing multiple files.

        Args:
            file_list (list[Path]): A list of file paths to be processed.

        Returns:
            list[Data]: A list of parsed data objects from the processed files.
        """

        def process_file(file_path: Path, *, silent_errors: bool = False) -> Data:
            try:
                return parse_text_file_to_data(str(file_path), silent_errors=silent_errors)
            except FileNotFoundError as e:
                msg = f"File not found: {file_path.name}. Error: {e}"
                self.log(msg)
                if not silent_errors:
                    raise e
                return None
            except Exception as e:
                msg = f"Unexpected error processing {file_path.name}: {e}"
                self.log(msg)
                if not silent_errors:
                    raise e
                return None

        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_count = len(file_list)

        if concurrency < 2 or file_count < 2:
            if file_count > 1:
                self.log(f"Processing {file_count} files sequentially.")
            processed_data = [process_file(file) for file in file_list if file]
        else:
            self.log(f"Starting parallel processing of {file_count} files with concurrency: {concurrency}.")
            processed_data = parallel_load_data(
                file_list,
                silent_errors=self.silent_errors,
                load_function=process_file,
                max_concurrency=concurrency,
            )

        # Filter out empty results and return
        return [data for data in processed_data if data]
