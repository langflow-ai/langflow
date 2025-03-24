from langflow.base.data import BaseFileComponent
from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.io import BoolInput, IntInput
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame


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

        def process_file(file_path: str, *, silent_errors: bool = False) -> Data | list[Data] | None:
            """Processes a single file and returns its Data object or list of Data objects."""
            try:
                # Check if it's a PDF file and we should use unstructured
                if file_path.lower().endswith('.pdf'):
                    return self._process_pdf_with_unstructured(file_path, silent_errors=silent_errors)
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

        # Flatten the processed_data if it contains lists of Data objects
        flattened_data = []
        for item in processed_data:
            if isinstance(item, list):
                flattened_data.extend(item)
            elif item is not None:
                flattened_data.append(item)

        # Use rollup_basefile_data to merge processed data with BaseFile objects
        return self.rollup_data(file_list, flattened_data)
    
    def _process_pdf_with_unstructured(self, file_path: str, *, silent_errors: bool = False) -> list[Data] | None:
        """Process PDF using unstructured library to extract structured data.
        
        Args:
            file_path (str): Path to the PDF file
            silent_errors (bool): Whether to silence errors
        
        Returns:
            list[Data]: List of Data objects, one for each element in the PDF
        """
        try:
            from unstructured.partition.pdf import partition_pdf
            import pandas as pd
            
            # Get PDF elements using unstructured
            elements = partition_pdf(file_path)
            
            element_data = [element.to_dict() for element in elements]
            
            # Convert to DataFrame
            df = pd.DataFrame(element_data)
            
            # Drop columns where all values are NA/null
            df = df.dropna(axis=1, how='all')
            
            if "element_id" in df.columns:
                df = df.drop("element_id", axis=1)
            
            # Convert DataFrame rows to a list of Data objects
            records = df.to_dict('records')
            data_list = [Data(data={**row, "file_path": file_path}) for row in records]
            
            # Return the list of Data objects
            return data_list
            
        except ImportError as e:
            msg = f"Could not import unstructured library: {e}. Please install with 'pip install unstructured[pdf]'"
            self.log(msg)
            if not silent_errors:
                raise
            return None
        except Exception as e:
            msg = f"Error processing PDF with unstructured: {e}"
            self.log(msg)
            if not silent_errors:
                raise
            return None
