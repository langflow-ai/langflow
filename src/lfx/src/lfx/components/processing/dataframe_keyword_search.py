import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DataFrameInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.dataframe import DataFrame


class DataFrameKeywordSearch(Component):
    display_name = "Keyword Search"
    description = "Search for keywords in a DataFrame column using any/all/coverage matching"
    icon = "Search"

    inputs = [
        DataFrameInput(
            name="dataframe",
            display_name="Table",
            info="Input table to search",
        ),
        MessageTextInput(
            name="column",
            display_name="Column",
            info=(
                "Column name to search in. Valid columns: 'file_path' (component file path) "
                "and 'text' (component source code)."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="keywords",
            display_name="Keywords",
            info="Keywords to search for",
            is_list=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="match_type",
            display_name="Match Type",
            options=["any", "all", "coverage"],
            value="any",
            info="'any' = OR logic, 'all' = AND logic, 'coverage' = keyword coverage ranking",
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            value=False,
            advanced=True,
            info="Whether search is case-sensitive",
        ),
        IntInput(
            name="number_candidates",
            display_name="Number of Candidates",
            value=10,
            info="The number of candidates to filter and return in the dataframe output",
        ),
    ]

    outputs = [
        Output(name="result", display_name="Filtered DataFrame", method="search"),
    ]

    def search(self) -> DataFrame:
        df = self.dataframe
        column = self.column
        keywords = self.keywords if isinstance(self.keywords, list) else []

        if df is None or len(df) == 0:
            return DataFrame(pd.DataFrame())

        if column not in df.columns:
            available = ", ".join(str(c) for c in df.columns)
            msg = f"Column '{column}' not found. Available columns: {available}"
            raise ValueError(msg)

        keywords = [str(k).strip() for k in keywords if k]
        if not keywords:
            return DataFrame(df)

        text_series = df[column].fillna("").astype(str)

        if not self.case_sensitive:
            text_series = text_series.str.lower()
            keywords = [k.lower() for k in keywords]

        if self.match_type == "any":
            mask = pd.Series([False] * len(df), index=df.index)
            for keyword in keywords:
                mask = mask | text_series.str.contains(keyword, regex=False)
            result = df[mask]
        elif self.match_type == "all":
            mask = pd.Series([True] * len(df), index=df.index)
            for keyword in keywords:
                mask = mask & text_series.str.contains(keyword, regex=False)
            result = df[mask]
        else:
            total_keywords = len(keywords)
            scores = [sum(1 for keyword in keywords if keyword in text) / total_keywords for text in text_series]
            result = df.copy()
            result["_score"] = scores
            result = result[result["_score"] > 0].sort_values("_score", ascending=False)

        return DataFrame(result.reset_index(drop=True)).head(self.number_candidates)
