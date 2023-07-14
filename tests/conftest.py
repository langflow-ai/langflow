import json
from pathlib import Path
from typing import AsyncGenerator
from langflow.api.v1.flows import get_session

from langflow.graph.graph.base import Graph
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool


def pytest_configure():
    pytest.BASIC_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "basic_example.json"
    )
    pytest.COMPLEX_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "complex_example.json"
    )
    pytest.OPENAPI_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "Openapi.json"
    )

    pytest.CODE_WITH_SYNTAX_ERROR = """
def get_text():
    retun "Hello World"
    """


@pytest.fixture()
async def async_client() -> AsyncGenerator:
    from langflow.main import create_app

    app = create_app()
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# Create client fixture for FastAPI
@pytest.fixture(scope="module")
def client():
    from langflow.main import create_app

    app = create_app()

    with TestClient(app) as client:
        yield client


def get_graph(_type="basic"):
    """Get a graph from a json file"""

    if _type == "basic":
        path = pytest.BASIC_EXAMPLE_PATH
    elif _type == "complex":
        path = pytest.COMPLEX_EXAMPLE_PATH
    elif _type == "openapi":
        path = pytest.OPENAPI_EXAMPLE_PATH

    with open(path, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    return Graph(nodes, edges)


@pytest.fixture
def basic_graph_data():
    with open(pytest.BASIC_EXAMPLE_PATH, "r") as f:
        return json.load(f)


@pytest.fixture
def basic_graph():
    return get_graph()


@pytest.fixture
def complex_graph():
    return get_graph("complex")


@pytest.fixture
def openapi_graph():
    return get_graph("openapi")


@pytest.fixture
def json_flow():
    with open(pytest.BASIC_EXAMPLE_PATH, "r") as f:
        return f.read()


@pytest.fixture(name="session")  #
def session_fixture():  #
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")  #
def client_fixture(session: Session):  #
    def get_session_override():  #
        return session

    from langflow.main import create_app

    app = create_app()

    app.dependency_overrides[get_session] = get_session_override  #

    yield TestClient(app)
    app.dependency_overrides.clear()  #


@pytest.fixture
def custom_chain():
    return '''from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Extra

from langchain.schema import BaseLanguageModel, Document
from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain.prompts import StringPromptTemplate
from langflow.interface.custom.base import CustomComponent

class MyCustomChain(Chain):
    """
    An example of a custom chain.
    """

    prompt: StringPromptTemplate
    """Prompt object to use."""
    llm: BaseLanguageModel
    output_key: str = "text"  #: :meta private:

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> List[str]:
        """Will be whatever keys the prompt expects.

        :meta private:
        """
        return self.prompt.input_variables

    @property
    def output_keys(self) -> List[str]:
        """Will always return text key.

        :meta private:
        """
        return [self.output_key]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        # Your custom chain logic goes here
        # This is just an example that mimics LLMChain
        prompt_value = self.prompt.format_prompt(**inputs)

        # Whenever you call a language model, or another chain, you should pass
        # a callback manager to it. This allows the inner run to be tracked by
        # any callbacks that are registered on the outer run.
        # You can always obtain a callback manager for this by calling
        # `run_manager.get_child()` as shown below.
        response = self.llm.generate_prompt(
            [prompt_value],
            callbacks=run_manager.get_child() if run_manager else None,
        )

        # If you want to log something about this run, you can do so by calling
        # methods on the `run_manager`, as shown below. This will trigger any
        # callbacks that are registered for that event.
        if run_manager:
            run_manager.on_text("Log something about this run")

        return {self.output_key: response.generations[0][0].text}

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        # Your custom chain logic goes here
        # This is just an example that mimics LLMChain
        prompt_value = self.prompt.format_prompt(**inputs)

        # Whenever you call a language model, or another chain, you should pass
        # a callback manager to it. This allows the inner run to be tracked by
        # any callbacks that are registered on the outer run.
        # You can always obtain a callback manager for this by calling
        # `run_manager.get_child()` as shown below.
        response = await self.llm.agenerate_prompt(
            [prompt_value],
            callbacks=run_manager.get_child() if run_manager else None,
        )

        # If you want to log something about this run, you can do so by calling
        # methods on the `run_manager`, as shown below. This will trigger any
        # callbacks that are registered for that event.
        if run_manager:
            await run_manager.on_text("Log something about this run")

        return {self.output_key: response.generations[0][0].text}

    @property
    def _chain_type(self) -> str:
        return "my_custom_chain"

class CustomChain(CustomComponent):
    display_name: str = "Custom Chain"
    field_config = {
        "prompt": {"field_type": "prompt"},
        "llm": {"field_type": "BaseLanguageModel"},
    }

    def build(self, prompt, llm, input: str) -> Document:
        chain = MyCustomChain(prompt=prompt, llm=llm)
        return chain(input)'''


@pytest.fixture
def data_processing():
    return """import pandas as pd
from langchain.schema import Document
from langflow.interface.custom.base import CustomComponent

class CSVLoaderComponent(CustomComponent):
    display_name: str = "CSV Loader"
    field_config = {
        "filename": {"field_type": "str", "required": True},
        "column_name": {"field_type": "str", "required": True},
    }

    def build(self, filename: str, column_name: str) -> List[Document]:
        # Load the CSV file
        df = pd.read_csv(filename)

        # Verify the column exists
        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in the CSV file")

        # Convert each row of the specified column to a document object
        documents = []
        for content in df[column_name]:
            metadata = {"filename": filename}
            documents.append(Document(page_content=str(content), metadata=metadata))

        return documents"""
