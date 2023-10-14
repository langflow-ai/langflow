from langflow import CustomComponent
from langchain.retrievers import AmazonKendraRetriever
from langchain.schema import BaseRetriever


class AmazonKendraRetrieverComponent(CustomComponent):
    display_name: str = "Amazon Kendra Retriever"
    description: str = "Retriever that uses the Amazon Kendra API."

    def build_config(self):
        return {
            "index_id": {"display_name": "Index ID"},
            "attribute_filter": {
                "attribute_filter": "Attribute Filter",
                "field_type": "code",
            },
            "code": {"show": False},
        }

    def build(
        self, index_id: str, attribute_filter: dict
    ) -> BaseRetriever:
        try:
            output = AmazonKendraRetriever(index_id=index_id, attribute_filter=attribute_filter)
        except Exception as e:
            raise ValueError("Could not connect to AmazonKendra API.") from e
        return output
