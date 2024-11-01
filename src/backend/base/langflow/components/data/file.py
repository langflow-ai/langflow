from pathlib import Path
from typing import IO
from zipfile import ZipFile, is_zipfile

from langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_data
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, Output
from langflow.schema import Data


class FileComponent(Component):
    """FileComponent handles the loading of generic files.

    Processes multiple valid files within a zip archive if provided.
    """

    display_name = "File"
    description = "Load a file to be used in your project."
    icon = "file-text"
    name = "File"

    inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=[*TEXT_FILE_TYPES, "zip"],  # Include 'zip' as a supported type
            info=f"Supported file types: {', '.join([*TEXT_FILE_TYPES, 'zip'])}",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_file"),
    ]

    def load_file(self) -> Data:
        """Load and parse a file or files from a zip archive.

        If the path points to a zip file, extract and process all valid files within it.
        """
        if not self.path:
            msg = "Please, upload a file to use this component."
            raise ValueError(msg)

        resolved_path = self.resolve_path(self.path)
        silent_errors = self.silent_errors

        if is_zipfile(resolved_path):
            return self._process_zip_file(resolved_path, silent_errors=silent_errors)

        # Process single non-zip file
        return self._process_single_file(resolved_path, silent_errors=silent_errors)

    def _process_zip_file(self, zip_path: Path, *, silent_errors: bool) -> Data:
        """Process all valid text files within a zip archive.

        Args:
            zip_path (Path): Path to the zip file.
            silent_errors (bool): If true, errors will not raise an exception.

        Returns:
            Data: Aggregated data from all valid files within the zip.
        """
        aggregated_data = Data()

        with ZipFile(zip_path, "r") as zip_file:
            # Filter out valid files from the zip
            valid_files = [
                file
                for file in zip_file.namelist()
                if Path(file).suffix[1:].lower() in TEXT_FILE_TYPES
            ]

            # Raise an error if no valid files are found
            if not valid_files:
                msg = "No supported file types found in the zip archive."
                raise ValueError(msg)

            for _, file_name in enumerate(valid_files, 1):
                with zip_file.open(file_name) as file:
                    try:
                        # Process each file within the zip
                        file_data = self._process_single_file(
                            file, file_name, silent_errors=silent_errors
                        )

                        # Aggregate data from all files
                        if file_data:
                            aggregated_data.append(file_data)
                    except ValueError as _:
                        # Log error and continue processing other files
                        if not silent_errors:
                            raise

                        continue

        return aggregated_data

    def _process_single_file(
        self,
        file_path_or_obj: Path | IO,
        file_name: str | None = None,
        *,
        silent_errors: bool,
    ) -> Data:
        """Process an individual file, whether from the file system or within a zip.

        Args:
            file_path_or_obj (Union[Path, ZipFile.open]): Path to the file or file object from zip.
            silent_errors (bool): If true, errors will not raise an exception.
            file_name (str, optional): Name of the file for error messaging.

        Returns:
            Data: Parsed data from the file.
        """
        try:
            # Determine and validate file extension
            file_path_str = file_name or (
                file_path_or_obj.name
                if hasattr(file_path_or_obj, "name")
                else str(file_path_or_obj)
            )
            extension = Path(file_path_str).suffix[1:].lower()

            # Raise an error if the file type is not supported
            if extension == "doc":
                msg = "doc files are not supported. Please save as .docx"
                raise ValueError(msg)
            if extension not in TEXT_FILE_TYPES:
                msg = f"Unsupported file type: {extension}"
                raise ValueError(msg)

            # Parse the file data
            data = parse_text_file_to_data(
                file_path_or_obj, silent_errors=silent_errors
            )

            # Log success or error message
            logging_info = (
                f"{file_name or file_path_or_obj} processed successfully"
                if data
                else f"No data in {file_name or file_path_or_obj}"
            )
            self.log(logging_info)

            # Update the component status
            self.status = data or Data()

            return data or Data()
        except Exception as e:
            error_message = (
                f"Error processing file {file_name or file_path_or_obj}: {e}"
            )

            # Raise an error or log the error message
            if not silent_errors:
                raise ValueError(error_message) from e

            self.status = error_message

            return Data()
