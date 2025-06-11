# mypy: disable-error-code="attr-defined"
from langchain_community.retrievers import AmazonKendraRetriever

from langflow.base.vectorstores.model import check_cached_vector_store
from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.io import DictInput, IntInput, StrInput


class AmazonKendraRetrieverComponent(CustomComponent):
    display_name: str = "Amazon Kendra Retriever"
    description: str = "Retriever that uses the Amazon Kendra API."
    name = "AmazonKendra"
    icon = "Amazon"
    legacy = True

    inputs = [
        StrInput(
            name="index_id",
            display_name="Index ID",
        ),
        StrInput(
            name="region_name",
            display_name="Region Name",
        ),
        StrInput(
            name="credentials_profile_name",
            display_name="Credentials Profile Name",
        ),
        DictInput(
            name="attribute_filter",
            display_name="Attribute Filter",
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=3,
        ),
        DictInput(
            name="user_context",
            display_name="User Context",
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> AmazonKendraRetriever:
        """Builds the Amazon Kendra Retriever."""
        try:
            from langchain_community.retrievers import AmazonKendraRetriever
        except ImportError as e:
            msg = "Could not import AmazonKendraRetriever. Please install it with `pip install langchain-community`."
            raise ImportError(msg) from e

        try:
            output = AmazonKendraRetriever(
                index_id=self.index_id,
                top_k=self.top_k,
                region_name=self.region_name,
                credentials_profile_name=self.credentials_profile_name,
                attribute_filter=self.attribute_filter,
                user_context=self.user_context,
            )
        except Exception as e:
            msg = "Could not connect to AmazonKendra API."
            raise ValueError(msg) from e

        return output
