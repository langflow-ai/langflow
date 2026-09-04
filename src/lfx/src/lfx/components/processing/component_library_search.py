from pathlib import Path

import pandas as pd

import lfx
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.dataframe import DataFrame


class ComponentLibrarySearch(Component):
    """Keyword search over the installed Langflow component library.

    The packaged assistant flow used to build this table with a ``Directory`` node pointed at
    the installed ``lfx/components`` directory. That path is outside every user's storage
    scope, so ``restrict_local_file_access`` denied it, and the node's search partner was
    inline flow code with no registered server counterpart, so ``allow_custom_components``
    denied that. Both denials were about the flow reaching for tenant-gated machinery to read
    first-party product source.

    Reading the library here removes the need for either exemption. There is no path input --
    the root is derived from this package -- so no tenant-controlled path exists for
    ``enforce_local_file_access`` to gate, and the component is registered like any other, so
    the custom-component gate resolves it normally. The source it returns is the same source
    ``GET /api/v1/all`` already serves to every authenticated user.
    """

    display_name = "Component Library Search"
    description = "Search for keywords in the installed component library using any/all/coverage matching"
    icon = "Search"

    inputs = [
        MessageTextInput(
            name="column",
            display_name="Column",
            info="Column name to search in. Valid columns: 'file_path' (component file path) "
            "and 'text' (component source code).",
            value="file_path",
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

    def _component_library(self) -> pd.DataFrame:
        """Read the installed component library into ``file_path`` / ``text`` columns.

        Mirrors what the flow's ``Directory`` node read before: the same ``*/*.py`` shape at
        depth 2, minus package ``__init__`` files, which carry only re-export boilerplate.
        Errors propagate rather than yielding a partial table -- an unreadable component file
        means a broken install, and a silently short search result reads as "no such
        component", which is a wrong answer rather than a visible failure.
        """
        root = (Path(lfx.__file__).parent / "components").resolve()
        if not root.is_dir():
            msg = f"Component library not found at {root}."
            raise ValueError(msg)

        rows = []
        for path in sorted(root.glob("*/*.py")):
            if path.name == "__init__.py":
                continue
            # ``glob`` follows symlinks, so a link named ``*.py`` inside the package would be
            # read from wherever it points. Nothing ships one, and creating one needs write
            # access to site-packages -- which is already game over -- but staying inside the
            # root we advertise is a one-line invariant rather than a trusted assumption.
            if not path.resolve().is_relative_to(root):
                continue
            rows.append({"file_path": str(path), "text": path.read_text(encoding="utf-8")})
        if not rows:
            # Reporting an empty library is the GH #13618 symptom this component exists to
            # avoid: the agent reads it as "no such component" and says so confidently.
            msg = f"Component library at {root} contains no readable component source."
            raise ValueError(msg)
        return pd.DataFrame(rows, columns=["file_path", "text"])

    @staticmethod
    def _normalized_keywords(raw: object) -> list[str]:
        """Coerce the tool's ``keywords`` argument to a non-empty list of search terms.

        A model routinely passes a bare string for a list-typed argument, which is an
        unambiguous single keyword rather than an error. Anything else is a malformed call:
        raise so the agent can correct itself, as the invalid-column path already does.
        Returning the unfiltered library instead would present arbitrary components as
        matches -- a confidently wrong answer rather than a visible failure.
        """
        if isinstance(raw, str):
            raw = [raw]
        elif not isinstance(raw, list):
            msg = f"keywords must be a list of strings, got {type(raw).__name__}."
            raise TypeError(msg)

        # Strip before testing for emptiness: a whitespace-only keyword strips to "" and
        # ``str.contains("")`` matches every row.
        keywords = [stripped for stripped in (str(k).strip() for k in raw) if stripped]
        if not keywords:
            msg = "keywords must contain at least one non-empty search term."
            raise ValueError(msg)
        return keywords

    def search(self) -> DataFrame:
        df = self._component_library()
        column = self.column
        match_type = self.match_type
        case_sensitive = self.case_sensitive

        if column not in df.columns:
            available = ", ".join(str(c) for c in df.columns)
            msg = f"Column '{column}' not found. Available columns: {available}"
            raise ValueError(msg)

        keywords = self._normalized_keywords(self.keywords)

        text_series = df[column].fillna("").astype(str)

        if not case_sensitive:
            text_series = text_series.str.lower()
            keywords = [k.lower() for k in keywords]

        if match_type == "any":
            mask = pd.Series([False] * len(df), index=df.index)
            for keyword in keywords:
                mask = mask | text_series.str.contains(keyword, regex=False)
            result = df[mask]

        elif match_type == "all":
            mask = pd.Series([True] * len(df), index=df.index)
            for keyword in keywords:
                mask = mask & text_series.str.contains(keyword, regex=False)
            result = df[mask]

        elif match_type == "coverage":
            scores = []
            total_keywords = len(keywords)

            for text in text_series:
                keywords_found = sum(1 for keyword in keywords if keyword in text)
                score = keywords_found / total_keywords
                scores.append(score)

            result = df.copy()
            result["_score"] = scores
            # Rank by score, then drop it: the documented output columns are file_path and
            # text, and coverage is the mode the shipped flow uses, so leaking the internal
            # ranking artifact would spend agent context on every returned row.
            result = result[result["_score"] > 0].sort_values("_score", ascending=False)
            result = result.drop(columns=["_score"])

        else:
            # Unreachable through the tool, which exposes only column and keywords, but a hand
            # edited flow can set anything. Say so rather than raising UnboundLocalError below.
            msg = f"Unknown match_type '{match_type}'. Expected one of: any, all, coverage."
            raise ValueError(msg)

        return DataFrame(result.reset_index(drop=True)).head(self.number_candidates)
