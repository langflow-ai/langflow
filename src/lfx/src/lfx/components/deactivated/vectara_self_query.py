# mypy: disable-error-code="attr-defined"
import json

from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever

from lfx.base.vectorstores.model import check_cached_vector_store
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.io import HandleInput, StrInput


class VectaraSelfQueryRetriverComponent(CustomComponent):
    """A custom component for implementing Vectara Self Query Retriever using a vector store."""

    display_name: str = "Vectara Self Query Retriever"
    description: str = "Implementation of Vectara Self Query Retriever"
    name = "VectaraSelfQueryRetriver"
    icon = "Vectara"
    legacy = True

    inputs = [
        HandleInput(
            name="vectorstore",
            display_name="Vector Store",
            info="Input Vectara Vector Store",
        ),
        HandleInput(
            name="llm",
            display_name="LLM",
            info="For self query retriever",
        ),
        StrInput(
            name="document_content_description",
            display_name="Document Content Description",
            info="For self query retriever",
        ),
        StrInput(
            name="metadata_field_info",
            display_name="Metadata Field Info",
            info="Each metadata field info is a string in the form of key value pair dictionary containing "
            "additional search metadata.\n"
            'Example input: {"name":"speech","description":"what name of the speech","type":'
            '"string or list[string]"}.\n'
            "The keys should remain constant(name, description, type)",
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self):
        """Builds the Vectara Self Query Retriever."""
        try:
            from langchain_community.vectorstores import Vectara  # noqa: F401
        except ImportError as e:
            msg = "Could not import Vectara. Please install it with `pip install langchain-community`."
            raise ImportError(msg) from e

        metadata_field_obj = []
        for meta in self.metadata_field_info:
            meta_obj = json.loads(meta)
            if "name" not in meta_obj or "description" not in meta_obj or "type" not in meta_obj:
                msg = "Incorrect metadata field info format."
                raise ValueError(msg)
            attribute_info = AttributeInfo(
                name=meta_obj["name"],
                description=meta_obj["description"],
                type=meta_obj["type"],
            )
            metadata_field_obj.append(attribute_info)

        return SelfQueryRetriever.from_llm(
            self.llm,  # type: ignore[attr-defined]
            self.vectorstore,  # type: ignore[attr-defined]
            self.document_content_description,  # type: ignore[attr-defined]
            metadata_field_obj,
            verbose=True,
        )
