import csv
import json
import logging
import os
import tempfile
from pathlib import Path
from xml.etree.ElementTree import Element
from zipfile import ZipFile, is_zipfile

import pandas as pd
from defusedxml import ElementTree as DefusedXML

from langflow.base.data import BaseFileComponent
from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.io import BoolInput, IntInput, Output
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class FileComponent(BaseFileComponent):
    display_name = "File"
    description = "Load and process various file types with support for multiple formats and structured outputs."
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
        Output(display_name="Structured Data", name="structured_data", method="get_structured_data"),
        Output(display_name="Raw Data", name="raw_data", method="get_raw_data"),
        Output(display_name="File Paths", name="file_paths", method="get_file_paths"),
    ]

    def _to_dataframe(self, data: Data | list[Data]) -> DataFrame:
        if isinstance(data, list):
            dataframe = pd.DataFrame([d.data for d in data])
        elif isinstance(data, Data):
            dataframe = pd.DataFrame([data.data])
        else:
            dataframe = pd.DataFrame()
        return DataFrame(dataframe)

    def get_structured_data(self) -> DataFrame:
        """Returns structured data from the file(s) as a DataFrame."""
        self.log("Getting structured data")
        result = self._process_file(structured=True)
        dataframe = self._to_dataframe(result)
        self.status = dataframe
        return dataframe

    def get_raw_data(self) -> Message:
        """Returns the raw content of the file as a Message."""
        self.log("Getting raw data")
        result = self._process_file(structured=False)
        raw_string = self._to_raw_string(result)
        self.status = raw_string
        return Message(text=raw_string)

    def _to_raw_string(self, data: Data | list[Data] | str) -> str:
        if isinstance(data, str):
            return data
        if isinstance(data, Data):
            if isinstance(data.data, dict):
                if "text_content" in data.data:
                    return str(data.data["text_content"])
                if "zip_contents" in data.data:
                    return "\n".join(self._to_raw_string(content) for content in data.data["zip_contents"])
            return str(data.data)
        if isinstance(data, list):
            return "\n".join(self._to_raw_string(item) for item in data)
        return str(data)

    def get_file_paths(self) -> Message:
        """Returns the resolved file paths as a Message."""
        path = Path(self.resolve_path(self._attributes["path"]))
        paths = self._extract_zip_paths(path) if is_zipfile(path) else [str(path)]
        file_paths_string = "\n".join(paths)
        self.status = file_paths_string
        return Message(text=file_paths_string)

    def _extract_zip_paths(self, zip_path: Path) -> list[str]:
        """Extract ZIP file and return paths of extracted files."""
        extracted_paths = []
        with tempfile.TemporaryDirectory() as tmpdirname, ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdirname)
            for root, _, files in os.walk(tmpdirname):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(Path(tmpdirname))
                    extracted_paths.append(f"{zip_path.name}/{relative_path}")
        return extracted_paths

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        """Processes files either sequentially or in parallel, depending on concurrency settings."""
        if not file_list:
            self.log("No files to process.")
            return file_list

        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_count = len(file_list)
        parallel_processing_threshold = 2

        if concurrency < parallel_processing_threshold or file_count < parallel_processing_threshold:
            if file_count > 1:
                self.log(f"Processing {file_count} files sequentially.")
            processed_data = []
            for _ in file_list:
                result = self._process_file(structured=True)
                if isinstance(result, list):
                    processed_data.extend(result)
                else:
                    processed_data.append(result)
        else:
            self.log(f"Starting parallel processing of {file_count} files with concurrency: {concurrency}.")
            file_paths = [str(file.path) for file in file_list]
            processed_data = parallel_load_data(
                file_paths, silent_errors=self.silent_errors, max_concurrency=concurrency
            )

        return self.rollup_data(file_list, processed_data)

    def _process_file(self, *, structured: bool = True) -> Data | list[Data] | str:
        """Process a single file or zip archive."""
        if not self._attributes.get("path"):
            msg = "Please upload a file for processing."
            raise ValueError(msg)

        path = Path(self.resolve_path(self._attributes["path"]))
        self.log(f"Processing file: {path}")

        if is_zipfile(path):
            return self._process_zip_file(zip_path=path, structured=structured)
        return self._process_single_file(file_path=path, structured=structured)

    def _process_zip_file(self, *, zip_path: Path, structured: bool) -> list[Data] | Data:
        """Process a zip file containing multiple files."""
        self.log("Processing ZIP file")
        data = []
        with tempfile.TemporaryDirectory() as tmpdirname, ZipFile(zip_path, "r") as zip_file:
            zip_file.extractall(tmpdirname)
            for root, _, files in os.walk(tmpdirname):
                for file_name in files:
                    file_path = Path(root) / file_name
                    if file_path.suffix.lower() == ".pdf":
                        self.log(f"Processing PDF in ZIP: {file_name}")
                        result = parse_text_file_to_data(str(file_path), silent_errors=self.silent_errors)
                        parsed_content = Data(data={"text_content": result.text if result else None})
                    elif any(file_name.endswith(ext) for ext in [*TEXT_FILE_TYPES, ".docx"]):
                        self.log(f"Processing ZIP content: {file_name}")
                        content = file_path.read_bytes()
                        parsed_content = self._parse_file_content(
                            file_name=file_name, content=content, structured=structured
                        )
                    else:
                        continue

                    if isinstance(parsed_content, list):
                        data.extend(parsed_content)
                    else:
                        data.append(parsed_content)

        if structured:
            return data
        return Data(data={"zip_contents": [d.data if isinstance(d, Data) else d for d in data]})

    def _process_single_file(self, *, file_path: Path, structured: bool) -> Data | list[Data] | str:
        """Process a single file."""
        try:
            if file_path.suffix.lower() == ".pdf":
                self.log("Processing PDF file")
                result = parse_text_file_to_data(str(file_path), silent_errors=self.silent_errors)
                return Data(data={"text_content": result.text if result else None})
            content = file_path.read_bytes()
            if file_path.suffix.lower() == ".docx" and not structured:
                self.log("Processing DOCX file in raw mode")
                return content.decode("utf-8", errors="ignore")
            return self._parse_file_content(file_name=file_path.name, content=content, structured=structured)
        except Exception as e:
            self.log(f"Error processing file: {e!s}")
            if self.silent_errors:
                return Data(data={"error": str(e)})
            raise

    def _parse_file_content(
        self, *, file_name: str, content: bytes, structured: bool = True
    ) -> Data | list[Data] | str:
        """Parse file content based on file extension."""
        file_extension = Path(file_name).suffix.lower()
        self.log(f"Parsing file content: {file_extension}")

        if not structured:
            return self._parse_raw(content)

        parser_map = {
            ".json": self._parse_json,
            ".csv": self._parse_csv,
            ".yaml": self._parse_yaml,
            ".yml": self._parse_yaml,
            ".xml": self._parse_xml,
            ".html": self._parse_html,
            ".htm": self._parse_html,
        }

        parser = parser_map.get(file_extension, self._parse_text)
        return parser(content=content, structured=structured)

    def _parse_raw(self, content: bytes) -> str:
        """Parse raw file content."""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            self.log("Falling back to latin-1 encoding")
            return content.decode("latin-1", errors="ignore")

    def _parse_json(self, *, content: bytes, structured: bool) -> Data | list[Data]:
        """Parse JSON content."""
        self.log("Parsing JSON content")
        parsed_data = json.loads(content.decode("utf-8"))
        if structured:
            if isinstance(parsed_data, list):
                return [Data(data=item) for item in parsed_data]
            return Data(data=parsed_data)
        return json.dumps(parsed_data, indent=2)

    def _parse_csv(self, *, content: bytes, structured: bool) -> list[Data] | str:
        """Parse CSV content."""
        self.log("Parsing CSV content")
        csv_reader = csv.DictReader(content.decode("utf-8").splitlines())
        if structured:
            return [Data(data=row) for row in csv_reader]
        csv_content = list(csv.reader(content.decode("utf-8").splitlines()))
        return "\n".join([",".join(row) for row in csv_content])

    def _parse_yaml(self, *, content: bytes, structured: bool) -> Data | str:
        """Parse YAML content."""
        yaml_content = content.decode("utf-8")
        return Data(data={"text_content": yaml_content}) if structured else yaml_content

    def _parse_xml(self, *, content: bytes, structured: bool) -> list[Data] | str:
        """Parse XML content."""
        root = DefusedXML.fromstring(content)
        if structured:
            return self._xml_to_list_data(root)
        return DefusedXML.tostring(root, encoding="unicode", method="xml")

    def _xml_to_list_data(self, element: Element) -> list[Data]:
        """Convert XML element to list of Data objects."""
        result = []
        for child in element:
            data = {}
            for subchild in child:
                if len(subchild) == 0:
                    data[subchild.tag] = subchild.text
                else:
                    data[subchild.tag] = self._xml_to_dict(subchild)
            result.append(Data(data=data))
        return result

    def _xml_to_dict(self, element: Element) -> dict:
        """Convert XML element to dictionary."""
        result = {}
        for child in element:
            if len(child) == 0:
                result[child.tag] = child.text
            else:
                result[child.tag] = self._xml_to_dict(child)
        return result

    def _parse_html(self, *, content: bytes, structured: bool) -> Data | str:
        """Parse HTML content."""
        html_content = content.decode("utf-8")
        return Data(data={"text_content": html_content}) if structured else html_content

    def _parse_text(self, *, content: bytes, structured: bool) -> Data | str:
        """Parse text content."""
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            self.log("Falling back to latin-1 encoding")
            text_content = content.decode("latin-1", errors="ignore")
        return Data(data={"text_content": text_content}) if structured else text_content

    def log(self, message: str) -> None:
        """Log a message with the component's name."""
        logging.info("[%s] %s", self.display_name, message)
