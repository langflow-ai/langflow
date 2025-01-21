from langflow.custom import Component
from langflow.io import Output, MessageTextInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from io import BytesIO 
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class WebSearchComponent(Component):
    display_name = "Web Search Component"
    description = "Use this component to generate a web search."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "WebSearchComponent"
    inputs = [
        MessageTextInput(name="query", display_name="Query", info="The query that will be searched", required=True),
        MessageTextInput(name="report_type", display_name="Report Type", info="The generated report style", required=False, value="research_report"),
        MessageTextInput(name="language", display_name="Language", info="The language of the result", required=False, value=""),
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="The requesting agent identifier", required=False, value="SYM"),
        # MessageTextInput(name="langfuse_metadata", display_name="Langfuse Metadata", info="User customized metadata that needs to be traced", required=False, value={}),
        # MessageTextInput(name="langfuse_keys", display_name="Langfuse Keys", info="Langfuse public and secret key", required=False, value={}),
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]

    def build_output_data(self) -> Data:
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}web_research/"

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        fields = {
            "query" : self.query,
            "report_type": self.report_type,
            "language": self.language,
            "requesting_agent":self.requesting_agent,
            "langfuse_metadata": {},
            "langfuse_keys": {}
        }
        response = http.request('POST', url, headers=headers, json=fields)
        result = json.loads(response.data.decode('utf-8'))
        srch_uuid = result.get('uuid', "")
        if srch_uuid:
            url_uuid = url + srch_uuid
            response_file = http.request('GET', url_uuid, headers=headers)
            content_disposition = response_file.headers.get('Content-Disposition', '')
            file_name = content_disposition.split('filename=')[-1].strip()
            file_stream = BytesIO(response_file.data)
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            file_path = os.path.join(downloads_dir, file_name)
            with open(file_path, 'wb') as f:
                f.write(file_stream.getvalue())
            return Data(value=f"File '{file_name}' downloaded successfully to {downloads_dir}.")


        data_obj = Data(value=f"UUID: {srch_uuid}")
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)