"""Simple component to load a DataFrame from a CSV URL."""

from langflow.custom import Component
from langflow.io import Output, StrInput
from langflow.schema import DataFrame
from loguru import logger
import pandas as pd


class CSVURLLoaderComponent(Component):
    display_name = "CSV Loader"
    description = "Load a DataFrame from a CSV URL"
    icon = "table"
    name = "CSVURLLoader"

    inputs = [
        StrInput(
            name="url",
            display_name="CSV URL",
            info="URL to the CSV file (HTTP/HTTPS)",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="load_csv"),
    ]

    def load_csv(self) -> DataFrame:
        """Load CSV from URL and return as DataFrame."""
        try:
            logger.info(f"Loading CSV from URL: {self.url}")
            
            # Read CSV directly from URL using pandas
            df = pd.read_csv(self.url)
            
            logger.info(f"Successfully loaded CSV with {len(df)} rows and {len(df.columns)} columns")
            
            # Convert pandas DataFrame to Langflow DataFrame
            return DataFrame(df)
            
        except Exception as e:
            error_msg = f"Error loading CSV from URL: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e