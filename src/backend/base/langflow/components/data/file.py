from copy import deepcopy
from typing import Any

from langflow.base.data.base_file import BaseFileComponent
from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.io import BoolInput, FileInput, IntInput, Output
from langflow.schema.data import Data


class FileComponent(BaseFileComponent):
    """Handles loading and processing of individual or zipped text files.

    This component supports processing multiple valid files within a zip archive,
    resolving paths, validating file types, and optionally using multithreading for processing.
    """

    display_name = "File"
    description = "Loads content from one or more files as a DataFrame."
    icon = "file-text"
    name = "File"

    VALID_EXTENSIONS = TEXT_FILE_TYPES

    _base_inputs = deepcopy(BaseFileComponent._base_inputs)

    for input_item in _base_inputs:
        if isinstance(input_item, FileInput) and input_item.name == "path":
            input_item.real_time_refresh = True
            break

    inputs = [
        *_base_inputs,
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
            advanced=True,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
    ]

    outputs = [
        Output(display_name="Raw Content", name="message", method="load_files_message"),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the number of files processed."""
        if field_name == "path":
            # Add outputs based on the number of files in the path
            if len(field_value) == 0:
                return frontend_node

            frontend_node["outputs"] = []

            if len(field_value) == 1:
                # We need to check if the file is structured content
                file_path = frontend_node["template"]["path"]["file_path"][0]
                if file_path.endswith((".csv", ".xlsx", ".parquet")):
                    frontend_node["outputs"].append(
                        Output(display_name="Structured Content", name="dataframe", method="load_files_structured"),
                    )
                elif file_path.endswith(".json"):
                    frontend_node["outputs"].append(
                        Output(display_name="Structured Content", name="json", method="load_files_json"),
                    )

                # All files get the raw content and path outputs
                frontend_node["outputs"].append(
                    Output(display_name="Raw Content", name="message", method="load_files_message"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path"),
                )
            else:
                # For multiple files, we only show the files output
                frontend_node["outputs"].append(
                    Output(display_name="Files", name="dataframe", method="load_files"),
                )

        return frontend_node

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Processes files either sequentially or in parallel, depending on concurrency settings.

        Args:
            file_list (list[BaseFileComponent.BaseFile]): List of files to process.

        Returns:
            list[BaseFileComponent.BaseFile]: Updated list of files with merged data.
        """

        def process_file(file_path: str, *, silent_errors: bool = False) -> Data | None:
            """Processes a single file and returns its Data object."""
            try:
                return parse_text_file_to_data(file_path, silent_errors=silent_errors)
            except FileNotFoundError as e:
                msg = f"File not found: {file_path}. Error: {e}"
                self.log(msg)
                if not silent_errors:
                    raise
                return None
            except Exception as e:
                msg = f"Unexpected error processing {file_path}: {e}"
                self.log(msg)
                if not silent_errors:
                    raise
                return None

        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_count = len(file_list)

        parallel_processing_threshold = 2
        if concurrency < parallel_processing_threshold or file_count < parallel_processing_threshold:
            if file_count > 1:
                self.log(f"Processing {file_count} files sequentially.")
            processed_data = [process_file(str(file.path), silent_errors=self.silent_errors) for file in file_list]
        else:
            self.log(f"Starting parallel processing of {file_count} files with concurrency: {concurrency}.")
            file_paths = [str(file.path) for file in file_list]
            processed_data = parallel_load_data(
                file_paths,
                silent_errors=self.silent_errors,
                load_function=process_file,
                max_concurrency=concurrency,
            )

        # Use rollup_basefile_data to merge processed data with BaseFile objects
        return self.rollup_data(file_list, processed_data)
