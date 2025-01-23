from langflow.custom import Component
from langflow.io import Output, MessageTextInput, IntInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
import time
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class EntityExtractionComponent(Component):
    display_name = "Entity Extraction Component"
    description = "Use this component to extract entities."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "pickax"
    name = "EntityExtractionComponent"
    inputs = [
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="Identifier for the system or user initiating the request (e.g., LLM8, EKA2, JAIME, etc.).", required=True),
        MessageTextInput(name="input_list", display_name="Input List", info="A list of input texts for entity extraction.", required=True),
        MessageTextInput(name="entity_schemas", display_name="Entity Schemas", info="A dictionary defining the schema for each entity.", required=True),
        MessageTextInput(name="entities_description", display_name="Entities Description", info="A dictionary providing descriptions for each entity.", required=False),
        MessageTextInput(name="examples", display_name="Examples", info="A list of example inputs for training the extraction model.", required=False),
        IntInput(name="k", display_name="K", info=" An integer specifying the number of top entities to extract.", required=False, value=-1),
        MessageTextInput(name="llm_model", display_name="Llm Model", info="Specifies the language model to be used for extraction", required=False),
        MessageTextInput(name="metadata", display_name="Metadata", info="Additional data that may be needed during extraction (e.g., username, department)", required=False),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]

    def build_output_data(self) -> Data:
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        input_list = json.loads(self.input_list) if self.input_list else []
        entity_schemas = json.loads(self.entity_schemas) if self.entity_schemas else {}
        examples = json.loads(self.examples) if self.examples else []
        metadata = json.loads(self.metadata) if self.metadata else {}
        url = f"{SDCP_ROOT_URL}entity_extraction/extract_entities/"

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        fields = {
            "requesting_agent" : self.requesting_agent,
            "input_list": input_list,
            "entity_schemas": entity_schemas,
            "entities_description":self.entities_description,
            "examples": examples,
            "k": self.k,
            "llm_model": self.llm_model,
            "metadata": metadata
        }
        response = http.request('POST', url, headers=headers, json=fields)
        result = json.loads(response.data.decode('utf-8'))
        ee_uuid = result.get('entity_extraction_uuid', "")
        if not ee_uuid:
            data_obj = Data(value=result)
            self.status = data_obj
        while True:
            url_uuid = url + ee_uuid
            response_uuid = http.request('GET', url_uuid, headers=headers, preload_content=False)
            status_result = json.loads(response_uuid.data.decode("utf-8"))
            status = status_result.get("status")
            if status == "Operation Completed successfully":
                data_uuid = Data(value=status_result.get("data"))
                return data_uuid
            elif status == "In Progress":
                time.sleep(10)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)