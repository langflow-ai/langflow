from pathlib import Path

from langflow.custom import Component
from langflow.io import DropdownInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame

KNOWLEDGE_BASES_DIR = "~/.langflow/knowledge_bases"
KNOWLEDGE_BASES_ROOT_PATH = Path(KNOWLEDGE_BASES_DIR).expanduser()


class KBRetrievalComponent(Component):
    display_name = "Retrieve KB"
    description = "Load a particular knowledge base."
    icon = "database"
    name = "KBRetrieval"

    inputs = [
        DropdownInput(
            name="knowledge_base",
            display_name="Knowledge Base",
            info="Select the knowledge base to load files from.",
            options=[
                str(d.name) for d in KNOWLEDGE_BASES_ROOT_PATH.iterdir() if not d.name.startswith(".") and d.is_dir()
            ]
            if KNOWLEDGE_BASES_ROOT_PATH.exists()
            else [],
            refresh_button=True,
        ),
        StrInput(
            name="kb_root_path",
            display_name="KB Root Path",
            info="Root directory for knowledge bases (defaults to ~/.langflow/knowledge_bases)",
            advanced=True,
            value=KNOWLEDGE_BASES_DIR,
        ),
    ]

    outputs = [
        Output(
            name="kb_info",
            display_name="Knowledge Base Info",
            method="retrieve_kb_info",
            info="Returns basic metadata of the selected knowledge base.",
        ),
        Output(
            name="kb_data",
            display_name="Knowledge Base Data",
            method="get_kb_data",
            info="Returns the data from the selected knowledge base.",
        ),  
    ]

    def _get_knowledge_bases(self) -> list[str]:
        """Retrieve a list of available knowledge bases.

        Returns:
            A list of knowledge base names.
        """
        # Return the list of directories in the knowledge base root path
        kb_root_path = Path(self.kb_root_path).expanduser()

        if not kb_root_path.exists():
            return []

        return [str(d.name) for d in kb_root_path.iterdir() if not d.name.startswith(".") and d.is_dir()]

    def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
        if field_name == "knowledge_base":
            # Update the knowledge base options dynamically
            build_config["knowledge_base"]["options"] = self._get_knowledge_bases()
            build_config["knowledge_base"]["value"] = None

        return build_config

    def retrieve_kb_info(self) -> DataFrame:
        """Retrieve basic metadata of the selected knowledge base.

        Returns:
            A DataFrame containing basic metadata of the knowledge base.
        """
        data = Data(
            name=self.knowledge_base,
            description=f"Metadata for {self.knowledge_base}",
            documents_count=0,
        )
        return DataFrame(data=[data])

    def get_kb_data(self) -> DataFrame:
        """Retrieve data from the selected knowledge base by reading the .parquet file in the knowledge base folder.

        Returns:
            A DataFrame containing the data rows from the knowledge base.
        """
        kb_root_path = Path(self.kb_root_path).expanduser()
        kb_path = kb_root_path / self.knowledge_base

        parquet_file = kb_path / "source.parquet"
        if not parquet_file.exists():
            msg = f"Parquet file not found: {parquet_file}"
            raise ValueError(msg)
        try:
            import pandas as pd
            parquet_df = pd.read_parquet(parquet_file).to_dict(orient="records")
            # Convert each record (dict) to a Data object, then create a DataFrame from the list of Data
            data_list = [Data(**record) for record in parquet_df]
            return DataFrame(data=data_list)

        except Exception as e:
            msg = f"Failed to open Parquet file '{parquet_file}': {e}"
            raise RuntimeError(msg) from e

