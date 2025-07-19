from langchain.agents.agent_toolkits.vectorstore.toolkit import VectorStoreInfo
from lfx.custom.custom_component.component import Component

from langflow.inputs.inputs import HandleInput, MessageTextInput, MultilineInput
from langflow.template.field.base import Output


class VectorStoreInfoComponent(Component):
    display_name = "VectorStoreInfo"
    description = "Information about a VectorStore"
    name = "VectorStoreInfo"
    legacy: bool = True
    icon = "LangChain"

    inputs = [
        MessageTextInput(
            name="vectorstore_name",
            display_name="Name",
            info="Name of the VectorStore",
            required=True,
        ),
        MultilineInput(
            name="vectorstore_description",
            display_name="Description",
            info="Description of the VectorStore",
            required=True,
        ),
        HandleInput(
            name="input_vectorstore",
            display_name="Vector Store",
            input_types=["VectorStore"],
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Vector Store Info", name="info", method="build_info"),
    ]

    def build_info(self) -> VectorStoreInfo:
        self.status = {
            "name": self.vectorstore_name,
            "description": self.vectorstore_description,
        }
        return VectorStoreInfo(
            vectorstore=self.input_vectorstore,
            description=self.vectorstore_description,
            name=self.vectorstore_name,
        )
