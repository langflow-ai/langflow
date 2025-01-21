from langflow.custom import Component
from langflow.io import Output
from langflow.inputs import FileInput, IntInput
from langflow.schema import Data
import requests
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class AudioEmbeddingComponent(Component):
    display_name="Audio Embedding"
    description= "Process audio file and generate embeddings"
    icon="special_component"
    name="AudioEmbedding"
    
    inputs=[
        FileInput(
            name= "audio_file",
            display_name="Audio File",
            info="An audio file to be processed.",
            required=True,
            file_types=["mp3","wav"]
        ),
        IntInput(
            name="split_length",
            display_name="Split Length",
            info="Split length in ms",
            value=60000
        )
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data")
    ]
    
    def build_output_data(self) -> Data:
        files ={'audio_file': open(self.audio_file, 'rb')} 
        data={"split_length":self.split_length}
        embedding_url=f"http://{SDCP_ROOT_URL}/embedding/audio-embedding"##PS: if you are using docker in windows url="http://host.docker.internal:8000/embedding/audio-embedding"
        embedding_result=requests.post(embedding_url,data=data,files=files)
        
        return Data(value=embedding_result.json())


    
    
    
    
    