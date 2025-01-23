from langflow.custom import Component
from langflow.io import MessageTextInput, Output, DropdownInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class ChunkingComponent(Component):
    display_name = "Chunking Component"
    description = "Use this component to split a list of documents or strings into smaller chunks."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "ChunkingComponent"
    
    inputs = [
        MessageTextInput(name="docs", display_name="Documents", info="The array of documents or strings to be chunked.", required=True),
        MessageTextInput(name="chunk_size", display_name="Chunk Size", info="The size of each chunk in characters.", required=False),
        MessageTextInput(name="chunk_overlap", display_name="Chunk Overlap", info="The size of overlap between chunks in characters.", required=False),
        DropdownInput(name="splitter", display_name="Splitter", info="Defines the type of chunking method to use.", options=["page", "sngl-char", "rec-chars", "tokens", "semantic"], value="rec-chars", required=False),
        MessageTextInput(name="llm_model", display_name="Llm Model", info="Specifies the language model to be used for semantic chunking.", required=False),
        DropdownInput(name="breakpoint", display_name="Breakpoint", info="Defines the type of breakpoint used to determine chunk boundaries.", options=["percentile", "standard_deviation", "interquartile", "gradient"], value="percentile", required=False),
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
        input_docs = self.docs
        chunk_size = None
        chunk_overlap = None
        if self.chunk_size and self.chunk_size.isdigit():
            chunk_size = int(self.chunk_size)
            if chunk_size < 16:
                chunk_size = None
        if self.chunk_overlap and self.chunk_overlap.isdigit() and int(self.chunk_overlap) > 0:
            chunk_overlap = int(self.chunk_overlap)
        splitter = self.splitter
        llm_model = self.llm_model
        break_point = self.breakpoint

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        base_url = f"{SDCP_ROOT_URL}chunking/chunking/"

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        query_params = []
        if chunk_size is not None:
            query_params.append(f"chunk_size={chunk_size}")
        if chunk_overlap is not None: 
            query_params.append(f"chunk_overlap={chunk_overlap}")
        query_params.append(f"splitter={splitter}")
        if llm_model:
            query_params.append(f"llm_model={llm_model}")
        query_params.append(f"breakpoint={break_point}")
        url = f"{base_url}?{'&'.join(query_params)}"
        response = http.request(
            'POST',
            url,
            headers=headers,
            body=input_docs
        )
        
        result = json.loads(response.data.decode('utf-8'))
        chunked_docs = result.get("chunks", [])
        data_obj = Data(value=f"Chunked Documents: {chunked_docs}")
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
