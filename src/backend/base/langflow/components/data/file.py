from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, is_zipfile

import fitz

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
        BoolInput(
            name="use_multithreading",
            display_name="Use Multithreading",
            advanced=True,
            info="If true, parallel processing will be enabled for zip files.",
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
                self.log(f"Processing zip file: {resolved_path.name}.")
                return self._process_zip_file(
                    resolved_path,
                    silent_errors=self.silent_errors,
                    parallel=self.use_multithreading,
                )

            self.log(f"Processing single file: {resolved_path.name}.")
            return self._process_single_file(resolved_path, silent_errors=self.silent_errors)
        except FileNotFoundError:
            self.log(f"File not found: {resolved_path.name}.")
            raise

    def _process_zip_file(self, zip_path: Path, *, silent_errors: bool = False, parallel: bool = False) -> Data:
        """Process text files within a zip archive.

        Args:
            zip_path: Path to the zip file.
            silent_errors: Suppresses errors if True.
            parallel: Enables parallel processing if True.

        Returns:
            list[Data]: Combined data from all valid files.

        Raises:
            ValueError: If no valid files found in the archive.
        """
        data: list[Data] = []
        with ZipFile(zip_path, "r") as zip_file:
            # Filter file names based on extensions in TEXT_FILE_TYPES and ignore hidden files
            valid_files = [
                name
                for name in zip_file.namelist()
                if (
                    any(name.endswith(ext) for ext in TEXT_FILE_TYPES)
                    and not name.startswith("__MACOSX")
                    and not name.startswith(".")
                )
            ]

            # Raise an error if no valid files found
            if not valid_files:
                self.log("No valid files in the zip archive.")

                # Return empty data if silent_errors is True
                if silent_errors:
                    return data  # type: ignore[return-value]

                # Raise an error if no valid files found
                msg = "No valid files in the zip archive."
                raise ValueError(msg)

            # Define a function to process each file
            def process_file(file_name):
                with NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = Path(temp_file.name).with_name(file_name)
                    with zip_file.open(file_name) as file_content:
                        temp_path.write_bytes(file_content.read())
                try:
                    return self._process_single_file(temp_path, silent_errors=silent_errors)
                finally:
                    temp_path.unlink()

            # Process files in parallel if specified
            if parallel:
                self.log("Initializing parallel Thread Pool Executor.")
                with ThreadPoolExecutor() as executor:
                    futures = {executor.submit(process_file, file): file for file in valid_files}
                    for future in as_completed(futures):
                        try:
                            data.append(future.result())
                        except Exception as e:
                            self.log(f"Error processing file {futures[future]}: {e}")
                            if not silent_errors:
                                raise
            else:
                # Sequential processing
                data.extend([process_file(file_name) for file_name in valid_files])

        self.log(f"Successfully processed zip file: {zip_path.name}.")

        return data  # type: ignore[return-value]

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

        # Define a function to extract text from a PDF file
        def pdf_to_text(filepath):
            text = ""

            # Open the PDF file
            with fitz.open(filepath) as pdf:
                for page in pdf:
                    text += page.get_text() + "\n"

            return text

        # Check if the file type is supported
        if not any(file_path.suffix == ext for ext in ["." + f for f in [*TEXT_FILE_TYPES, "pdf"]]):
            self.log(f"Unsupported file type: {file_path.suffix}")

            # Return empty data if silent_errors is True
            if silent_errors:
                return Data()

            msg = f"Unsupported file type: {file_path.suffix}"
            raise ValueError(msg)

        try:
            # Parse the file based on the file type
            if file_path.suffix == ".pdf":
                data = Data(data={"file_path": file_path, "text": pdf_to_text(file_path)})
            else:
                data = parse_text_file_to_data(str(file_path), silent_errors=silent_errors)  # type: ignore[assignment]
                if not data:
                    data = Data()

            self.log(f"Successfully processed file: {file_path.name}.")
        except Exception as e:
            self.log(f"Error processing file {file_path.name}: {e}")

            # Return empty data if silent_errors is True
            if not silent_errors:
                raise

            data = Data()

        return data
