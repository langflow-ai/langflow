from langflow.custom import Component
from langflow.io import MessageTextInput,Output
from langflow.inputs import DropdownInput,FileInput
from langflow.schema import Data
import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class ImageEmbeddingsComponent(Component):
    display_name="Image Embeddings"
    description= "API endpoint to initiate the embedding process for a list of image files or image URLs"
    icon="special_component"
    name="ImageEmbeddings"
    
    inputs=[
        DropdownInput(
            name= "gpt_model_name",
            display_name="Gpt Model Name",
            options=["gpt-4o","gpt-4o-mini","gpt-4-turbo"],
            info="The GPT model name to use for processing.",
            required=True
        ),
        FileInput(
            name= "image_files",
            display_name="Image Files",
            info="A list of image files to be processed.",
            required=True,
            file_types=["jpg","png","jpeg"],
        ),
        MessageTextInput(
            name="image_urls",
            display_name="Image Urls",
            info="A list of image URLs to be processed.",
            required=True
        )
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data")
    ]
    
    def build_output_data(self) -> Data:
        files ={'image_files': open(self.image_files, 'rb')} 
        data={"gpt_model_name":self.gpt_model_name,"image_urls":[self.image_urls]}
        embedding_url = f"http://{SDCP_ROOT_URL}/embedding/image_embeddings"
        embedding_result=requests.post(embedding_url,data=data,files=files)
        job_id=embedding_result.json().get("process_id")
        time.sleep(10)
        embedding_job_url = f"http://{SDCP_ROOT_URL}/embedding/image_embeddings/{job_id}"
        embedding_job_result=requests.get(embedding_job_url)
        status=embedding_job_result.json().get("status")
        while status == "In Progress":
            time.sleep(10)
            embedding_job_result=requests.get(embedding_job_url)
            status=embedding_job_result.json().get("status")
        
        return Data(value=embedding_job_result.json())


    
    
    
    
    