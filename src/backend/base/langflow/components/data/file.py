from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, is_zipfile

from langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_data
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, Output
from langflow.schema import Data


class FileComponent(Component):
    """Handles loading of individual or zipped text files.

    Processes multiple valid files within a zip archive if provided.

    Attributes:
        display_name: Display name of the component.
        description: Brief component description.
        icon: Icon to represent the component.
        name: Identifier for the component.
        inputs: Inputs required by the component.
        outputs: Output of the component after processing files.
    """

    display_name = "File"
    description = "Load a file to be used in your project."
    icon = "file-text"
    name = "File"

    inputs = [
        FileInput(
            name="path",
            display_name="Path",
            file_types=[*TEXT_FILE_TYPES, "zip"],
            info=f"Supported file types: {', '.join([*TEXT_FILE_TYPES, 'zip'])}",
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            advanced=True,
            info="If true, errors will not raise an exception.",
        ),
    ]

    outputs = [Output(display_name="Data", name="data", method="load_file")]

    def load_file(self) -> Data:
        """Load and parse file(s) from a zip archive.

        Raises:
            ValueError: If no file is uploaded or file path is invalid.

        Returns:
            Data: Parsed data from file(s).
        """
        # Check if the file path is provided
        if not self.path:
            self.log("File path is missing.")

            msg = "Please upload a file for processing."
            raise ValueError(msg)

        resolved_path = Path(self.resolve_path(self.path))
        try:
            # Check if the file is a zip archive
            if is_zipfile(resolved_path):
                self.log("Processing zip file at %s.", str(resolved_path))

                return self._process_zip_file(resolved_path, silent_errors=self.silent_errors)

            self.log("Processing single file at %s.", str(resolved_path))

            return self._process_single_file(resolved_path, silent_errors=self.silent_errors)
        except FileNotFoundError as _:
            self.log("File not found: %s", resolved_path)

            raise

    def _process_zip_file(self, zip_path: Path, *, silent_errors: bool = False) -> Data:
        """Process text files within a zip archive.

        Args:
            zip_path: Path to the zip file.
            silent_errors: Suppresses errors if True.

        Returns:
            Data: Combined data from all valid files.

        Raises:
            ValueError: If no valid files found in the archive.
        """
        data: list[Data] = []
        with ZipFile(zip_path, "r") as zip_file:
            # Filter file names based on extensions in TEXT_FILE_TYPES
            valid_files = [name for name in zip_file.namelist() if any(name.endswith(ext) for ext in TEXT_FILE_TYPES)]
            if not valid_files:
                msg = "No valid files in the zip archive."
                self.log(msg)

                # Return an empty data object if silent errors is True
                if silent_errors:
                    return data

                # Raise an exception if silent errors is False
                raise ValueError(msg)

            # Parse the content of each valid file
            for file_name in valid_files:
                file_extension = Path(file_name).suffix
                with zip_file.open(file_name) as file_content:
                    with NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(file_content.read())
                        temp_path = Path(temp_file.name)
                        self.log(str(temp_path))

                    try:
                        # Process the temporary file
                        data.append(self._process_single_file(temp_path, silent_errors=silent_errors))
                    finally:
                        # Clean up the temporary file after processing
                        temp_path.unlink()

        self.log(f"Successfully processed zip file: {zip_path}.")

        return data

    def _process_single_file(self, file_path: Path, *, silent_errors: bool = False) -> Data:
        """Process a single file.

        Args:
            file_path: Path to the file.
            silent_errors: Suppresses errors if True.

        Returns:
            Data: Parsed data from the file.

        Raises:
            ValueError: For unsupported file formats.
        """
        if not any(file_path.suffix == ext for ext in ["." + f for f in TEXT_FILE_TYPES]):
            msg = f"Unsupported file type: {file_path.suffix}"
            self.log(msg)

            # Return an empty data object if silent errors is True
            if silent_errors:
                return Data()

            # Raise an exception if silent errors is False
            raise ValueError(msg)

        try:
            # Parse the file content
            data = parse_text_file_to_data(str(file_path), silent_errors=silent_errors)
            self.log(f"Successfully processed file: {file_path}.")

        except Exception as e:
            self.log(f"Error processing file {file_path!s}: {e}")
            if not silent_errors:
                raise

            data = Data()

        return data
