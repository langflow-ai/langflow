import csv
import io
from pathlib import Path

from langflow.custom import Component
from langflow.io import FileInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data


class CSVToDataComponent(Component):
    display_name = "CSV to Data List"
    description = "Load a CSV file, CSV from a file path, or a valid CSV string and convert it to a list of Data"
    icon = "file-spreadsheet"
    beta = True
    name = "CSVtoData"

    inputs = [
        FileInput(
            name="csv_file",
            display_name="CSV File",
            file_types=["csv"],
            info="Upload a CSV file to convert to a list of Data objects",
        ),
        MessageTextInput(
            name="csv_path",
            display_name="CSV File Path",
            info="Provide the path to the CSV file as pure text",
        ),
        MultilineInput(
            name="csv_string",
            display_name="CSV String",
            info="Paste a CSV string directly to convert to a list of Data objects",
        ),
    ]

    outputs = [
        Output(name="data_list", display_name="Data List", method="load_csv_to_data"),
    ]

    def load_csv_to_data(self) -> list[Data]:
        if sum(bool(field) for field in [self.csv_file, self.csv_path, self.csv_string]) != 1:
            msg = "Please provide exactly one of: CSV file, file path, or CSV string."
            raise ValueError(msg)

        csv_data = None
        try:
            if self.csv_file:
                resolved_path = self.resolve_path(self.csv_file)
                file_path = Path(resolved_path)
                if file_path.suffix.lower() != ".csv":
                    self.status = "The provided file must be a CSV file."
                else:
                    with file_path.open(newline="", encoding="utf-8") as csvfile:
                        csv_data = csvfile.read()

            elif self.csv_path:
                file_path = Path(self.csv_path)
                if file_path.suffix.lower() != ".csv":
                    self.status = "The provided file must be a CSV file."
                else:
                    with file_path.open(newline="", encoding="utf-8") as csvfile:
                        csv_data = csvfile.read()

            else:
                csv_data = self.csv_string

            if csv_data:
                csv_reader = csv.DictReader(io.StringIO(csv_data))
                result = [Data(data=row) for row in csv_reader]

                if not result:
                    self.status = "The CSV data is empty."
                    return []

                self.status = result
                return result

        except csv.Error as e:
            error_message = f"CSV parsing error: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        except Exception as e:
            error_message = f"An error occurred: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        # An error occurred
        raise ValueError(self.status)
