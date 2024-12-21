import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from nv_ingest_client.client import NvIngestClient
from nv_ingest_client.primitives import JobSpec
from nv_ingest_client.primitives.tasks import ExtractTask, SplitTask
from nv_ingest_client.util.file_processing.extract import EXTENSION_TO_DOCUMENT_TYPE, extract_file_content

from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, MessageTextInput, Output, StrInput
from langflow.schema import Data

logger = logging.getLogger(__name__)


class NVIDIAIngestComponent(Component):
    display_name = "NV-Ingest"
    description = "Ingest documents"
    documentation: str = "https://github.com/NVIDIA/nv-ingest/tree/main/docs"
    icon = "NVIDIA"
    name = "NVIDIAIngest"
    beta = True

    file_types = list(EXTENSION_TO_DOCUMENT_TYPE.keys())
    supported_file_types_info = f"Supported file types: {', '.join(file_types)}"

    inputs = [
        StrInput(
            name="base_url",
            display_name="NVIDIA Ingestion URL",
            info="The URL of the NVIDIA Ingestion API.",
        ),
        FileInput(
            name="path",
            display_name="Path",
            file_types=file_types,
            info=supported_file_types_info,
        ),
        BoolInput(
            name="extract_text",
            display_name="Extract text?",
            info="Extract text or not",
            value=True,
        ),
        BoolInput(
            name="extract_images",
            display_name="Extract images?",
            info="Extract images or not",
            value=False,
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract tables?",
            info="Extract tables or not",
            value=True,
        ),
        BoolInput(
            name="split_text",
            display_name="Split text?",
            info="Split text into smaller chunks?",
            value=True,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap",
            info="Number of characters to overlap between chunks.",
            value=200,
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The maximum number of characters in each chunk.",
            value=1000,
            advanced=True,
        ),
        MessageTextInput(
            name="separator",
            display_name="Separator",
            info="The character to split on. Defaults to newline.",
            value="\n",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_file"),
    ]

    def load_file(self) -> Data:
        if not self.path:
            err_msg = "Please, upload a file to use this component."
            raise ValueError(err_msg)
        resolved_path = self.resolve_path(self.path)

        extension = Path(resolved_path).suffix[1:].lower()

        if extension not in self.file_types:
            err_msg = f"Unsupported file type: {extension}"
            raise ValueError(err_msg)

        file_content, file_type = extract_file_content(resolved_path)

        job_spec = JobSpec(
            document_type=file_type,
            payload=file_content,
            source_id=self.path,
            source_name=self.path,
            extended_options={"tracing_options": {"trace": True, "ts_send": time.time_ns()}},
        )

        extract_task = ExtractTask(
            document_type=file_type,
            extract_text=self.extract_text,
            extract_images=self.extract_images,
            extract_tables=self.extract_tables,
        )

        job_spec.add_task(extract_task)

        if self.split_text:
            split_task = SplitTask(
                split_by="word",
                split_length=self.chunk_size,
                split_overlap=self.chunk_overlap,
                max_character_length=self.chunk_size,
                sentence_window_size=0,
            )
            job_spec.add_task(split_task)

        parsed_url = urlparse(self.base_url)
        message = f"creating NvIngestClient for host: {parsed_url.hostname}, port: {parsed_url.port}"
        self.log(message, name="NVIDIAIngestComponent")
        client = NvIngestClient(message_client_hostname=parsed_url.hostname, message_client_port=parsed_url.port)

        job_id = client.add_job(job_spec)

        client.submit_job(job_id, "morpheus_task_queue")

        result = client.fetch_job_result(job_id, timeout=60)
        result_str = str(result)
        msg = f"results: {result_str}"
        self.log(msg, name="NVIDIAIngestComponent")

        data = []

        for element in result[0]:
            if element["document_type"] == "text":
                data.append(
                    Data(
                        text=element["metadata"]["content"],
                        file_path=element["metadata"]["source_metadata"]["source_name"],
                        document_type=element["document_type"],
                        description=element["metadata"]["content_metadata"]["description"],
                    )
                )
            elif element["document_type"] == "structured":
                data.append(
                    Data(
                        text=element["metadata"]["table_metadata"]["table_content"],
                        file_path=element["metadata"]["source_metadata"]["source_name"],
                        document_type=element["document_type"],
                        description=element["metadata"]["content_metadata"]["description"],
                    )
                )
            # TODO: handle images

        self.status = data if data else "No data"
        return data or Data()
