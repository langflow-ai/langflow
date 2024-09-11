from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import csv
from io import StringIO


class CSVToDataComponent(Component):
    display_name = "CSV to Data"
    description = "Convert a CSV string to a list of Data objects"
    icon = "📊"
    beta = True
    name = "CSVtoData"

    inputs = [
        MessageTextInput(
            name="csv_string",
            display_name="CSV String",
            info="Enter a valid CSV string to convert to a list of Data objects",
        ),
    ]

    outputs = [
        Output(name="data_list", display_name="Data List", method="convert_csv_to_data"),
    ]

    def convert_csv_to_data(self) -> list[Data]:
        try:
            csv_string = self.csv_string

            # Use StringIO to create a file-like object from the string
            csv_file = StringIO(csv_string)

            # Create a CSV reader object
            csv_reader = csv.DictReader(csv_file)

            # Convert each row to a Data object
            result = []
            for row in csv_reader:
                result.append(Data(data=row))

            self.status = result
            return result

        except csv.Error as e:
            error_message = f"CSV parsing error: {str(e)}"
            self.status = error_message
            return [Data(data={"error": error_message})]

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            self.status = error_message
            return [Data(data={"error": error_message})]
