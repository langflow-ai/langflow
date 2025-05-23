from langflow.custom import Component
from langflow.io import DataFrameInput, MultilineInput, Output, StrInput
from langflow.schema.message import Message


class ParseDataFrameComponent(Component):
    display_name = "Parse DataFrame"
    description = (
        "Convert a DataFrame into plain text following a specified template. "
        "Each column in the DataFrame is treated as a possible template key, e.g. {col_name}."
    )
    icon = "braces"
    name = "ParseDataFrame"
    legacy = True

    inputs = [
        DataFrameInput(name="df", display_name="DataFrame", info="The DataFrame to convert to text rows."),
        MultilineInput(
            name="template",
            display_name="Template",
            info=(
                "The template for formatting each row. "
                "Use placeholders matching column names in the DataFrame, for example '{col1}', '{col2}'."
            ),
            value="{text}",
        ),
        StrInput(
            name="sep",
            display_name="Separator",
            advanced=True,
            value="\n",
            info="String that joins all row texts when building the single Text output.",
        ),
    ]

    outputs = [
        Output(
            display_name="Text",
            name="text",
            info="All rows combined into a single text, each row formatted by the template and separated by `sep`.",
            method="parse_data",
        ),
    ]

    def _clean_args(self):
        dataframe = self.df
        template = self.template or "{text}"
        sep = self.sep or "\n"
        return dataframe, template, sep

    def parse_data(self) -> Message:
        """Converts each row of the DataFrame into a formatted string using the template.

        then joins them with `sep`. Returns a single combined string as a Message.
        """
        dataframe, template, sep = self._clean_args()

        lines = []
        # For each row in the DataFrame, build a dict and format
        for _, row in dataframe.iterrows():
            row_dict = row.to_dict()
            text_line = template.format(**row_dict)  # e.g. template="{text}", row_dict={"text": "Hello"}
            lines.append(text_line)

        # Join all lines with the provided separator
        result_string = sep.join(lines)
        self.status = result_string  # store in self.status for UI logs
        return Message(text=result_string)
