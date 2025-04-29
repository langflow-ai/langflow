import numpy as np
import pandas as pd
from sklearn.metrics import classification_report

from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, Output
from langflow.schema import DataFrame


class ClassificationReportComponent(Component):
    display_name = "Classification Report"
    description = "Generate a classification report with precision, recall, f1-score, and support metrics"
    documentation = "https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report.html"
    icon = "ScikitLearn"
    report_data = None

    inputs = [
        HandleInput(
            name="y_true",
            display_name="True Labels",
            info="Ground truth (correct) target values",
            input_types=["DataFrame", "list", "numpy.ndarray"],
        ),
        HandleInput(
            name="y_pred",
            display_name="Predicted Labels",
            info="Estimated targets as returned by a classifier",
            input_types=["DataFrame", "list", "numpy.ndarray"],
        ),
        BoolInput(
            name="output_dict",
            display_name="Output as Dictionary",
            info="If True, return output as dict instead of string",
            value=True,
        ),
    ]

    outputs = [
        Output(display_name="Classification Report", name="report", method="get_classification_report"),
        Output(display_name="Report DataFrame", name="report_dataframe", method="get_report_dataframe"),
    ]

    def process_input(self, input_data):
        """Convert input to numpy array regardless of input type."""
        if isinstance(input_data, DataFrame):
            return input_data.to_numpy().ravel()
        if isinstance(input_data, list):
            return np.array(input_data)
        if isinstance(input_data, np.ndarray):
            return input_data.ravel()
        msg = f"Unsupported input type: {type(input_data)}"
        raise TypeError(msg)

    def generate_report(self):
        if not hasattr(self, "y_true") or not hasattr(self, "y_pred"):
            msg = "Both true labels and predicted labels must be provided."
            raise ValueError(msg)

        # Process inputs to ensure they're in the correct format
        y_true = self.process_input(self.y_true)
        y_pred = self.process_input(self.y_pred)

        # Generate the classification report
        self.report_data = classification_report(
            y_true,
            y_pred,
            output_dict=self.output_dict,
        )

    def get_classification_report(self) -> dict:
        """Return the classification report as a dictionary."""
        if self.report_data is None:
            self.generate_report()
        return self.report_data

    def get_report_dataframe(self) -> DataFrame:
        """Return the classification report as a formatted DataFrame."""
        if self.report_data is None:
            self.generate_report()

        if isinstance(self.report_data, str):
            # If the report is a string (when output_dict=False), return it as a single-cell DataFrame
            return DataFrame(pd.DataFrame({"Classification Report": [self.report_data]}))

        # Convert dictionary to DataFrame
        df_report = pd.DataFrame(self.report_data).transpose()

        # Reorder columns to a more logical sequence if they exist
        preferred_order = ["precision", "recall", "f1-score", "support"]
        columns = [col for col in preferred_order if col in df_report.columns]
        df_report = df_report[columns]

        # Convert support to integer if it exists
        if "support" in df_report.columns:
            df_report["support"] = df_report["support"].astype(int)

        return DataFrame(df_report)
