from langflow.custom import Component
from langflow.io import Output
from langflow.inputs import FileInput, IntInput
from langflow.schema import Data
import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class GenerateVideoEmbeddingsComponent(Component):
    display_name="Generate Video Embeddings"
    description= "Generate Video Embeddings with setting frame range"
    icon="special_component"
    name="GenerateVideoEmbeddings"
    
    inputs=[
        FileInput(
            name= "video_file",
            display_name="Video File",
            info="A video file for embedding generation.",
            required=True,
            file_types=["mp4","avi","webm"]
        ),
        IntInput(
            name="frame_interval",
            display_name="Frame Interval",
            info="take frame on each frame interval in s",
            value=5
        )
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data")
    ]
    
    def build_output_data(self) -> Data:
        files ={'video_file': open(self.video_file, 'rb')} 
        data={"frame_interval":self.frame_interval}
        generation_embedding_url = f"{SDCP_ROOT_URL}video_processor/generate_video_embeddings"
        generation_embedding_result=requests.post(generation_embedding_url,data=data,files=files)
        job_id=generation_embedding_result.json().get("job_id")
        status=generation_embedding_result.json().get("status")
        embedding_job_url = f"{SDCP_ROOT_URL}video_processor/generate_video_embeddings/{job_id}"
        time.sleep(20)
        while status in  ["in_progress","In Progress"]:
            embedding_job_result=requests.get(embedding_job_url)
            status=embedding_job_result.json().get("status")
            time.sleep(20)
        
        return Data(value=embedding_job_result.json())