from typing import cast

from langchain_community.retrievers import AmazonKendraRetriever

from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.field_typing import Retriever


class AmazonKendraRetrieverComponent(CustomComponent):
    display_name: str = "Amazon Kendra Retriever"
    description: str = "Retriever that uses the Amazon Kendra API."
    name = "AmazonKendra"
    icon = "Amazon"
    legacy: bool = True

    def build_config(self):
        return {
            "index_id": {"display_name": "Index ID"},
            "region_name": {"display_name": "Region Name"},
            "credentials_profile_name": {"display_name": "Credentials Profile Name"},
            "attribute_filter": {
                "display_name": "Attribute Filter",
                "field_type": "code",
            },
            "top_k": {"display_name": "Top K", "field_type": "int"},
            "user_context": {
                "display_name": "User Context",
                "field_type": "code",
            },
            "code": {"show": False},
        }

    def build(
        self,
        index_id: str,
        top_k: int = 3,
        region_name: str | None = None,
        credentials_profile_name: str | None = None,
        attribute_filter: dict | None = None,
        user_context: dict | None = None,
    ) -> Retriever:  # type: ignore[type-var]
        try:
            output = AmazonKendraRetriever(
                index_id=index_id,
                top_k=top_k,
                region_name=region_name,
                credentials_profile_name=credentials_profile_name,
                attribute_filter=attribute_filter,
                user_context=user_context,
            )
        except Exception as e:
            msg = "Could not connect to AmazonKendra API."
            raise ValueError(msg) from e
        return cast("Retriever", output)
