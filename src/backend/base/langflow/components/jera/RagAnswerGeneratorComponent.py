from langflow.custom import Component
from langflow.io import Output, MessageTextInput, MultilineInput
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
 
 
class RagAnswerGeneratorComponent(Component):
    display_name = "User Question Answer Generator Rag Component"
    description = "Use this component to answer your question using Rag."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "RagAnswerGeneratorComponent"
 
    inputs = [
        MessageTextInput(
            name="question",
            display_name="your Question",
            info="the user question",
        ),
        MultilineInput(
            name="docs",
            display_name="A list of documents to be used for answer generation.",
            info="the user documents",
        ),
        MessageTextInput(name="retriever_top_n", display_name=" Max number of subqueries", info="The number of top documents to retrieve"),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
 
    def build_output_data(self) -> Data:
        question = self.question
        retriever_top_n = self.retriever_top_n
        docs = self.docs.split('\n')
       
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}answer_generator/generate_answer/"

        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        # Prepare the fields for application/json
        fields = {
            'requesting_agent': "langflow",
            'persona': "string",
            'langfuse_metadata': {},
            'langfuse_keys': {},
            'question': question,
            'docs': docs,
            'retriever_top_n': retriever_top_n
        }
        encoded_data = json.dumps(fields).encode('utf-8')

        response = http.request('POST', url, body=encoded_data, headers=headers)
        result = json.loads(response.data.decode('utf-8'))

        data_obj = Data(value=result["answer"])
       
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
 
 