# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput, MessageInput
from langflow.io import Output
from langflow.schema import Data
from typing import Dict, Any
from twelvelabs import TwelveLabs
import time
import json

class TwelveLabsTextEmbeddings(Component):
    display_name = "Twelve Labs Text Embeddings"
    description = "Converts text content to embeddings using Twelve Labs API."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "text"
    name = "TwelveLabsTextEmbeddings"

    inputs = [
        DataInput(
            name="textdata", 
            display_name="Text Data", 
            info="Text data to embed",
            is_list=True
        ),
        SecretStrInput(
            name="api_key",
            display_name="Twelve Labs API Key",
            info="Enter your Twelve Labs API Key."
        )
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="generate_embeddings"),
    ]

    def wait_for_task_completion(
        self, 
        client: TwelveLabs, 
        task_id: str, 
        max_retries: int = 60, 
        sleep_time: int = 5
    ) -> Dict[str, Any]:
        """Wait for task completion with timeout.
        
        Args:
            client: TwelveLabs client instance
            task_id: ID of the task to monitor
            max_retries: Maximum number of retry attempts
            sleep_time: Time to wait between retries in seconds
            
        Returns:
            Dict containing the task result
            
        Raises:
            Exception: If task fails or times out
        """
        retries = 0
        while retries < max_retries:
            try:
                self.log("Checking task status (attempt {})".format(retries + 1))
                result = client.embed.task.retrieve(id=task_id)
                
                if result.status == "ready":
                    self.log("Task completed successfully!")
                    return result
                elif result.status == "failed":
                    error_msg = f"Task failed with status: {result.status}"
                    self.log(error_msg, "ERROR")
                    raise Exception(error_msg)
                
                time.sleep(sleep_time)
                retries += 1
                status_msg = f"Processing text... {retries * sleep_time}s elapsed"
                self.status = status_msg
                self.log(status_msg)
                
            except Exception as e:
                error_msg = f"Error checking task status: {str(e)}"
                self.log(error_msg, "ERROR")
                raise Exception(error_msg)
        
        timeout_msg = f"Timeout after {max_retries * sleep_time} seconds"
        self.log(timeout_msg, "ERROR")
        raise Exception(timeout_msg)


    def generate_embeddings(self) -> Data:
        try:
            self.log("Starting text embedding process")
            
            if not self.textdata:
                self.log("No text data provided", "ERROR")
                return Data(value={"error": "No text data provided"})

            if not isinstance(self.textdata, list):
                self.log("Text data must be a list", "ERROR")
                return Data(value={"error": "Text data must be a list"})

            if not self.api_key:
                self.log("No API key provided", "ERROR")
                return Data(value={"error": "No API key provided"})

            self.log(f"Initializing client with API key: {self.api_key[:4]}...")
            client = TwelveLabs(api_key=self.api_key)

            all_embeddings = []
            
            for text_item in self.textdata:
                # Extract text from the data structure
                if hasattr(text_item, 'data'):
                    data = text_item.data
                    if isinstance(data, str):
                        text = data
                    elif isinstance(data, dict) and 'text' in data:
                        text = data['text']
                    else:
                        self.log(f"Invalid text item format: {text_item}", "ERROR")
                        continue
                else:
                    self.log(f"Invalid text item format: {text_item}", "ERROR")
                    continue

                self.log(f"Processing text: {text[:100]}...")

                result = client.embed.create(
                    model_name="Marengo-retrieval-2.7",
                    text=text
                )

                if (result.text_embedding is not None and 
                    result.text_embedding.segments is not None):
                    
                    segments = result.text_embedding.segments
                    for segment in segments:
                        embedding = {
                            'text': text,
                            'embedding': [float(x) for x in segment.embeddings_float]
                        }
                        all_embeddings.append(embedding)
                        
                        # Log truncated embedding
                        self.log(f"Generated embedding (first 5 values): {embedding['embedding'][:5]}")
                        self.log(f"Embedding dimension: {len(embedding['embedding'])}")

            status_msg = f"Generated {len(all_embeddings)} text embeddings"
            self.status = status_msg
            self.log(status_msg)

            self.status = json.dumps(all_embeddings)
            return Data(value={'embeddings': all_embeddings})
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.status = error_msg
            self.log(error_msg, "ERROR")
            return Data(value={"error": str(e)})
