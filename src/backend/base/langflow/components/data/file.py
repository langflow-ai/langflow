import asyncio
import os

from platformdirs import user_cache_dir

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
            advanced=True,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Processes files either sequentially or in parallel, depending on concurrency settings.

        Args:
            file_list (list[BaseFileComponent.BaseFile]): List of files to process.

        Returns:
            list[BaseFileComponent.BaseFile]: Updated list of files with merged data.
        """

        def process_file(file_path: str, *, silent_errors: bool = False, base_file=None) -> Data | None:
            """Processes a single file and returns its Data object."""
            try:
                # Skip macOS-specific hidden files
                if os.path.basename(file_path).startswith("._"):
                    return None

                # Try to get original_filename from the BaseFile's data
                original_filename = None
                if base_file is not None and base_file.data:
                    # base_file.data is a list of Data objects
                    for data_obj in base_file.data:
                        if isinstance(data_obj, Data):
                            # First try to get from data.original_filename
                            original_filename = data_obj.data.get("original_filename")
                            if not original_filename:
                                # Then try to get from data.data.original_filename
                                original_filename = data_obj.data.get("data", {}).get("original_filename")
                            if original_filename:
                                break

                # If we still don't have the original filename, try to get it from the database
                if not original_filename:
                    try:
                        from sqlmodel import select

                        from langflow.services.database.models.file import File as UserFile
                        from langflow.services.deps import get_db_service

                        db = get_db_service()
                        # Convert absolute path to relative path
                        cache_root = user_cache_dir("langflow", "langflow")
                        relative_path = os.path.relpath(file_path, start=cache_root)

                        async def get_filename():
                            async with db.with_session() as session:
                                stmt = select(UserFile).where(UserFile.path == relative_path)
                                result = await session.exec(stmt)
                                file_record = result.first()
                                if file_record:
                                    # Append the extension from the path
                                    extension = os.path.splitext(file_record.path)[1]
                                    return file_record.name + extension
                            return None

                        original_filename = asyncio.run(get_filename())
                    except Exception:
                        pass

                result = parse_text_file_to_data(
                    file_path, silent_errors=silent_errors, original_filename=original_filename
                )
                if result and result.data:
                    return result
            except FileNotFoundError as e:
                msg = f"File not found: {file_path}. Error: {e}"
                if not silent_errors:
                    raise
                return None
            except Exception as e:
                msg = f"Unexpected error processing {file_path}: {e}"
                if not silent_errors:
                    raise ValueError(msg) from e
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
            processed_data = [
                process_file(str(file.path), silent_errors=self.silent_errors, base_file=file) for file in file_list
            ]
        else:
            self.log(f"Starting parallel processing of {file_count} files with concurrency: {concurrency}.")
            # For parallel, we need to pass base_file as well, so use a lambda
            processed_data = parallel_load_data(
                [(str(file.path), file) for file in file_list],
                silent_errors=self.silent_errors,
                load_function=lambda args, silent_errors: process_file(
                    args[0], silent_errors=silent_errors, base_file=args[1]
                ),
                max_concurrency=concurrency,
            )

        # Use rollup_basefile_data to merge processed data with BaseFile objects
        return self.rollup_data(file_list, processed_data)
