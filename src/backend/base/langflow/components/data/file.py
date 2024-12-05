import io
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from zipfile import ZipFile, is_zipfile

import pandas as pd

from langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_data
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, Output
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message

SUPPORTED_FILE_TYPES = [
    "json",
    "csv",
    "yaml",
    "yml",
    "txt",
    "md",
    "mdx",
    "xml",
    "html",
    "htm",
    "pdf",
    "docx",
    "py",
    "sh",
    "sql",
    "js",
    "ts",
    "tsx",
    "zip",
]


class FileComponent(Component):
    display_name = "File"
    description = "Load and process various file types with support for multiple formats and structured outputs."
    icon = "file-text"
    name = "File"
    VALID_EXTENSIONS = SUPPORTED_FILE_TYPES

    inputs = [
        FileInput(
            name="path",
            display_name="File",
            file_types=SUPPORTED_FILE_TYPES,
            required=True,
        ),
        BoolInput(
            name="silent_errors",
            display_name="Silent Errors",
            info="If true, errors will not raise an exception.",
            advanced=True,
        ),
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
        Output(display_name="DataFrame", name="dataframe", method="get_dataframe"),
        Output(display_name="Raw Data", name="raw_data", method="get_raw_data"),
        Output(display_name="File Paths", name="file_paths", method="get_file_paths"),
    ]

    def resolve_path(self, path: str) -> str:
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        current_dir = os.getcwd()
        resolved_path = os.path.join(current_dir, path)
        return os.path.normpath(resolved_path)

    def _flatten_dict(self, d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
        items: list = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _normalize_data(self, data: dict[str, Any] | Data) -> dict[str, Any]:
        if isinstance(data, Data):
            data = data.data

        if isinstance(data, dict):
            # Extrai apenas os parágrafos do conteúdo processado
            if "paragraphs" in data:
                return {"paragraphs": "\n".join(data["paragraphs"])}
            return self._flatten_dict(data)
        if isinstance(data, str):
            return {"content": data}
        return {"content": str(data)}

    def _to_dataframe(self, data: Data | list[Data]) -> DataFrame:
        if isinstance(data, list):
            normalized_data = [self._normalize_data(d) for d in data]
            if not normalized_data:
                return DataFrame(pd.DataFrame())

            df = pd.DataFrame(normalized_data)

        elif isinstance(data, Data):
            normalized_data = self._normalize_data(data)
            df = pd.DataFrame([normalized_data])
        else:
            df = pd.DataFrame()

        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(json.dumps)

        return DataFrame(df)

    def get_dataframe(self) -> DataFrame:
        self.log("Getting structured data")
        result = self._process_file(structured=True)

        # Garantir que os dados estão no formato correto antes de criar o DataFrame
        if isinstance(result, Data):
            data = [self._normalize_data(result)]
        elif isinstance(result, list):
            data = [self._normalize_data(item) for item in result]
        else:
            self.log("Unexpected data format for structured data")
            data = []

        # Criar o DataFrame de forma segura
        if data:
            df = pd.DataFrame(data)
        else:
            # Se a lista 'data' estiver vazia, criamos um DataFrame com uma coluna de erro
            df = pd.DataFrame(columns=["Error"], data=["No data found"])

        # Change this line to avoid the ambiguous truth value error
        self.status = df.to_dict(orient="records")  # Convert DataFrame to string
        return DataFrame(df)

    def get_raw_data(self) -> Message:
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
                return json.dumps(data.data, indent=2)
            return str(data.data)
        if isinstance(data, list):
            return "\n".join(self._to_raw_string(item) for item in data)
        return str(data)

    def get_file_paths(self) -> Message:
        path = Path(self.resolve_path(self.path))
        if is_zipfile(path):
            paths = self._extract_zip_paths(path)
        else:
            paths = [str(path)]
        file_paths_string = "\n".join(paths)
        self.status = file_paths_string
        return Message(text=file_paths_string)

    def _extract_zip_paths(self, zip_path: Path) -> list[str]:
        extracted_paths = []
        with tempfile.TemporaryDirectory() as tmpdirname:
            with ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdirname)
                for root, _, files in os.walk(tmpdirname):
                    for file in files:
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, tmpdirname)
                        extracted_paths.append(f"{zip_path.name}/{relative_path}")
        return extracted_paths

    def _process_file(self, structured: bool = True) -> Data | list[Data] | str:
        if not self.path:
            raise ValueError("Please upload a file for processing.")

        path = Path(self.resolve_path(self.path))
        self.log(f"Processing file: {path}")

        if is_zipfile(path):
            return self._process_zip_file(path, structured)
        return self._process_single_file(path, structured)

    def _process_zip_file(self, zip_path: Path, structured: bool) -> list[Data] | Data:
        self.log("Processing ZIP file")
        data = []
        with tempfile.TemporaryDirectory() as tmpdirname:
            with ZipFile(zip_path, "r") as zip_file:
                zip_file.extractall(tmpdirname)
                for root, _, files in os.walk(tmpdirname):
                    for file_name in files:
                        file_path = Path(os.path.join(root, file_name))
                        if file_path.suffix.lower() == ".pdf":
                            self.log(f"Processing PDF in ZIP: {file_name}")
                            result = parse_text_file_to_data(str(file_path), silent_errors=self.silent_errors)
                            parsed_content = Data(data={"text_content": result.text if result else None})
                        elif any(file_name.endswith(ext) for ext in TEXT_FILE_TYPES + [".docx"]):
                            self.log(f"Processing ZIP content: {file_name}")
                            with open(file_path, "rb") as file:
                                content = file.read()
                                parsed_content = self._parse_file_content(file_name, content, structured)
                        else:
                            continue

                        if isinstance(parsed_content, list):
                            data.extend(parsed_content)
                        else:
                            data.append(parsed_content)

        if structured:
            return data
        return Data(data={"zip_contents": [d.data if isinstance(d, Data) else d for d in data]})

    def _process_single_file(self, file_path: Path, structured: bool) -> Data | list[Data] | str:
        try:
            if file_path.suffix.lower() == ".pdf":
                self.log("Processing PDF file")
                result = parse_text_file_to_data(str(file_path), silent_errors=self.silent_errors)
                return Data(data={"text_content": result.text if result else None})
            with open(file_path, "rb") as f:
                content = f.read()
                return self._parse_file_content(file_path.name, content, structured)
        except Exception as e:
            self.log(f"Error processing file: {e!s}")
            if self.silent_errors:
                return Data(data={"error": str(e)})
            raise

    def _parse_file_content(self, file_name: str, content: bytes, structured: bool = True) -> Data | list[Data] | str:
        file_extension = Path(file_name).suffix.lower()
        self.log(f"Parsing file content: {file_extension}")

        parser_map = {
            ".json": self._parse_json,
            ".csv": self._parse_csv,
            ".yaml": self._parse_yaml,
            ".yml": self._parse_yaml,
            ".xml": self._parse_xml,
            ".html": self._parse_html,
            ".htm": self._parse_html,
            ".docx": self._parse_docx,
        }

        parser = parser_map.get(file_extension, self._parse_text)
        return parser(content, structured)

    def _parse_json(self, content: bytes, structured: bool) -> Data | list[Data] | str:
        self.log("Parsing JSON content")
        try:
            parsed_data = json.loads(content.decode("utf-8"))
            if structured:
                if isinstance(parsed_data, list):
                    return [Data(data=item) for item in parsed_data]
                return Data(data=parsed_data)
            return json.dumps(parsed_data, indent=2)
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing error: {e!s}"
            self.log(error_msg)
            if self.silent_errors:
                return Data(data={"error": error_msg})
            raise

    def _parse_csv(self, content: bytes, structured: bool) -> list[Data] | str:
        self.log("Parsing CSV content")
        try:
            df = pd.read_csv(
                io.StringIO(content.decode("utf-8")),
                dtype_backend="numpy_nullable",
                parse_dates=True,
                infer_datetime_format=True,
            )

            if structured:
                column_types = {}
                for column in df.columns:
                    if df[column].dtype.name.startswith(("int", "uint")):
                        column_types[column] = "integer"
                    elif df[column].dtype.name.startswith("float"):
                        column_types[column] = "float"
                    elif df[column].dtype.name == "boolean":
                        column_types[column] = "boolean"
                    elif df[column].dtype.name == "datetime64[ns]":
                        column_types[column] = "datetime"
                    else:
                        column_types[column] = "string"

                data = []
                for _, row in df.iterrows():
                    processed_row = {}
                    for column in df.columns:
                        value = row[column]

                        if pd.isna(value):
                            processed_row[column] = None
                            continue

                        if column_types[column] == "integer":
                            processed_row[column] = int(value)
                        elif column_types[column] == "float":
                            processed_row[column] = float(value)
                        elif column_types[column] == "boolean":
                            processed_row[column] = bool(value)
                        elif column_types[column] == "datetime":
                            processed_row[column] = pd.Timestamp(value).isoformat()
                        elif isinstance(value, str):
                            try:
                                processed_row[column] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                processed_row[column] = str(value)
                        else:
                            processed_row[column] = str(value)

                    data.append(Data(data={"values": processed_row, "column_types": column_types}))
                return data
            return df.to_csv(index=False)

        except Exception as e:
            error_msg = f"CSV parsing error: {e!s}"
            self.log(error_msg)
            if self.silent_errors:
                return Data(data={"error": error_msg})
            raise

    def _parse_yaml(self, content: bytes, structured: bool) -> Data | list[Data] | str:
        try:
            import yaml

            yaml_content = content.decode("utf-8")
            if structured:
                parsed_data = yaml.safe_load(yaml_content)
                if isinstance(parsed_data, list):
                    return [Data(data=item) for item in parsed_data]
                if isinstance(parsed_data, dict):
                    return Data(data=parsed_data)
                return Data(data={"content": parsed_data})
            return yaml_content
        except Exception as e:
            error_msg = f"YAML parsing error: {e!s}"
            self.log(error_msg)
            if self.silent_errors:
                return Data(data={"error": error_msg})
            raise

    def _parse_xml(self, content: bytes, structured: bool) -> list[Data] | str:
        try:
            root = ET.fromstring(content)
            if structured:
                return self._xml_to_list_data(root)
            return ET.tostring(root, encoding="unicode", method="xml")
        except ET.ParseError as e:
            error_msg = f"XML parsing error: {e!s}"
            self.log(error_msg)
            if self.silent_errors:
                return Data(data={"error": error_msg})
            raise

    def _xml_to_list_data(self, element: ET.Element) -> list[Data]:
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

    def _xml_to_dict(self, element: ET.Element) -> dict:
        result = {}
        for child in element:
            if len(child) == 0:
                result[child.tag] = child.text
            else:
                result[child.tag] = self._xml_to_dict(child)
        return result

    def _parse_html(self, content: bytes, structured: bool) -> Data | str:
        html_content = content.decode("utf-8")
        if not structured:
            return html_content

        try:
            root = ET.fromstring(html_content)

            title = None
            title_elem = root.find(".//title")
            if title_elem is not None:
                title = title_elem.text

            def extract_text(element, exclude_tags={"script", "style"}):
                if element.tag in exclude_tags:
                    return ""
                text = (element.text or "").strip()
                for child in element:
                    text += " " + extract_text(child, exclude_tags)
                    if child.tail:
                        text += " " + child.tail.strip()
                return text.strip()

            def extract_structured_data(element):
                data = {"tag": element.tag, "attributes": dict(element.attrib), "text": (element.text or "").strip()}

                children = []
                for child in element:
                    child_data = extract_structured_data(child)
                    if child_data:
                        children.append(child_data)

                if children:
                    data["children"] = children

                if element.tail:
                    data["tail"] = element.tail.strip()

                return data

            structured_data = {
                "title": title,
                "text": extract_text(root),
                "structure": extract_structured_data(root),
                "metadata": {
                    "links": [a.get("href") for a in root.findall(".//a") if a.get("href")],
                    "images": [img.get("src") for img in root.findall(".//img") if img.get("src")],
                    "headers": [
                        h.text.strip()
                        for h in root.findall(".//*")
                        if h.tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and h.text
                    ],
                },
            }

            return Data(data=structured_data)

        except ET.ParseError:
            return Data(data={"text": html_content})

    def _strip_namespaces(self, data: dict) -> dict:
        """Remove XML namespaces from the keys."""

        def clean_key(key):
            if isinstance(key, ET.QName):
                return key.localname  # Remove namespace
            if isinstance(key, str) and "}" in key:
                return key.split("}", 1)[1]
            return key

        def clean_dict(d):
            if isinstance(d, dict):
                return {clean_key(k): clean_dict(v) for k, v in d.items()}
            if isinstance(d, list):
                return [clean_dict(item) for item in d]
            return d

        return clean_dict(data)

    def _parse_docx(self, content: bytes, structured: bool) -> Data | str:
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            paragraphs = []
            with ZipFile(temp_path, "r") as docx:
                if "word/document.xml" in docx.namelist():
                    doc_xml = docx.read("word/document.xml")
                    root = ET.fromstring(doc_xml)

                    for p in root.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                        paragraph_text = "".join(
                            node.text.strip() if node.text else ""
                            for node in p.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
                        )
                        if paragraph_text:
                            paragraphs.append(paragraph_text)

            os.unlink(temp_path)

            structured_data = {"paragraphs": paragraphs}

            if structured:
                return Data(data=structured_data)
            return "\n".join(paragraphs)

        except Exception as e:
            error_msg = f"DOCX parsing error: {e!s}"
            self.log(error_msg)
            if self.silent_errors:
                return Data(data={"error": error_msg})
            raise

    def _process_docx_element(self, elem: ET.Element) -> dict | None:
        tag = elem.tag.split("}")[-1]

        if tag == "p":
            return self._process_docx_paragraph(elem)
        if tag == "tbl":
            return self._process_docx_table(elem)
        return None

    def _process_docx_paragraph(self, p_elem: ET.Element) -> dict:
        p_data = {
            "type": "paragraph",
            "style": p_elem.find(".//{*}pStyle").get("{*}val") if p_elem.find(".//{*}pStyle") is not None else "normal",
            "content": [],
        }

        for r in p_elem.findall(".//{*}r"):
            run_data = {"text": "", "formatting": {}, "properties": {}}

            rPr = r.find(".//{*}rPr")
            if rPr is not None:
                for prop in rPr:
                    prop_name = prop.tag.split("}")[-1]
                    run_data["formatting"][prop_name] = True

            for t in r.findall(".//{*}t"):
                preserve = t.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"
                text = t.text or ""
                run_data["text"] += text if preserve else text.strip()

            if run_data["text"] or run_data["formatting"]:
                p_data["content"].append(run_data)

        return p_data

    def _process_docx_table(self, tbl_elem: ET.Element) -> dict:
        table_data = {"type": "table", "properties": {}, "rows": []}

        tblPr = tbl_elem.find(".//{*}tblPr")
        if tblPr is not None:
            for prop in tblPr:
                prop_name = prop.tag.split("}")[-1]
                table_data["properties"][prop_name] = True

        for tr in tbl_elem.findall(".//{*}tr"):
            row = []
            for tc in tr.findall(".//{*}tc"):
                cell_content = []
                for p in tc.findall(".//{*}p"):
                    p_data = self._process_docx_paragraph(p)
                    if p_data["content"]:
                        cell_content.append(p_data)
                row.append(cell_content)
            table_data["rows"].append(row)

        return table_data

    def _parse_text(self, content: bytes, structured: bool) -> Data | str:
        text_content = content.decode("utf-8", errors="ignore")
        if structured:
            return Data(data={"text": text_content})
        return text_content

    def log(self, message: str) -> None:
        print(f"[{self.display_name}] {message}")
