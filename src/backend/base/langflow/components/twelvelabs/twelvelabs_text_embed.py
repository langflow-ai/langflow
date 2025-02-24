# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data
from twelvelabs import TwelveLabs

class TwelveLabsTextEmbeddings(Component):
    display_name = "Twelve Labs Text Embeddings"
    description = "Converts text content to embeddings using Twelve Labs API."
    icon = "text"
    name = "TwelveLabsTextEmbeddings"

    inputs = [
        DataInput(
            name="textdata", 
            display_name="Text Data", 
            info="Text data to embed",
            is_list=True,
            required=True
        ),
        SecretStrInput(
            name="api_key",
            display_name="Twelve Labs API Key",
            info="Enter your Twelve Labs API Key.",
            required=True
        )
    ]

    outputs = [
        Output(display_name="Embeddings Data", name="embeddings", method="generate_embeddings"),
    ]

    def generate_embeddings(self) -> Data:
        try:
            if not self.textdata or not isinstance(self.textdata, list) or not self.api_key:
                return Data(value={"error": "Invalid input parameters"})

            client = TwelveLabs(api_key=self.api_key)
            all_embeddings = []
            
            for text_item in self.textdata:
                if not hasattr(text_item, 'data'):
                    continue
                    
                data = text_item.data
                text = data if isinstance(data, str) else data.get('text', '')
                if not text:
                    continue

                result = client.embed.create(
                    model_name="Marengo-retrieval-2.7",
                    text=text
                )

                if result.text_embedding and result.text_embedding.segments:
                    for segment in result.text_embedding.segments:
                        all_embeddings.append({
                            'text': text,
                            'embedding': [float(x) for x in segment.embeddings_float]
                        })

            return Data(value={'embeddings': all_embeddings})
            
        except Exception as e:
            return Data(value={"error": str(e)})
