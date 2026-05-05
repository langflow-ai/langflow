"""Table class for lfx package — pandas DataFrame subclass for tabular data.

The real `class Table(pandas.DataFrame)` is materialized lazily on first
use. Importing this module (e.g. `from lfx.schema.dataframe import Table`
or `from lfx.schema.dataframe import DataFrame`) does **not** load pandas.
That saves ~10s of cold-start time on flows that never actually touch a
DataFrame, which is most of them.

Triggers that DO load pandas (in order of how callers usually hit them):
  - `Table(data=...)` / `DataFrame(data=...)`
  - `Table.from_dict(...)` and other forwarded classmethods
  - `isinstance(x, Table)` where `x` is a pandas.DataFrame — but `isinstance`
    uses `sys.modules.get("pandas")` and only returns True when pandas is
    already loaded elsewhere, so the check itself never imports pandas.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd
    from langchain_core.documents import Document

    from lfx.schema.data import Data
    from lfx.schema.message import Message


_real_table_class: type | None = None


def _get_real_table() -> type:
    """Materialize the real pandas-backed Table class the first time it's needed."""
    global _real_table_class  # noqa: PLW0603
    if _real_table_class is not None:
        return _real_table_class

    import pandas as pd
    from langchain_core.documents import Document
    from pandas import DataFrame as pandas_DataFrame

    from lfx.schema.data import Data

    class Table(pandas_DataFrame):  # type: ignore[no-redef]
        """A pandas DataFrame subclass specialized for handling collections of JSON objects."""

        def __init__(
            self,
            data: list[dict] | list[Data] | pd.DataFrame | None = None,
            text_key: str = "text",
            default_value: str = "",
            **kwargs: Any,
        ):
            super().__init__(**kwargs)
            self._text_key = text_key
            self._default_value = default_value

            if data is None:
                return
            if isinstance(data, list):
                if all(isinstance(x, Data) for x in data):
                    data = [d.data for d in data if hasattr(d, "data")]
                elif not all(isinstance(x, dict) for x in data):
                    msg = "List items must be either all Data objects or all dictionaries"
                    raise ValueError(msg)
                self._update(data, **kwargs)
            elif isinstance(data, dict | pd.DataFrame):
                self._update(data, **kwargs)

        def _update(self, data: Any, **kwargs: Any) -> None:
            new_df = pd.DataFrame(data, **kwargs)
            self._update_inplace(new_df)

        @property
        def text_key(self) -> str:
            return self._text_key

        @text_key.setter
        def text_key(self, value: str) -> None:
            if value not in self.columns:
                msg = f"Text key '{value}' not found in Table columns"
                raise ValueError(msg)
            self._text_key = value

        @property
        def default_value(self) -> str:
            return self._default_value

        @default_value.setter
        def default_value(self, value: str) -> None:
            self._default_value = value

        def to_data_list(self) -> list[Data]:
            list_of_dicts = self.to_dict(orient="records")
            return [Data(data=row) for row in list_of_dicts]

        def add_row(self, data: dict | Data) -> Table:
            if isinstance(data, Data):
                data = data.data
            new_df = self._constructor([data])
            return pd.concat([self, new_df], ignore_index=True)  # type: ignore[return-value]

        def add_rows(self, data: list[dict | Data]) -> Table:
            processed_data = []
            for item in data:
                if isinstance(item, Data):
                    processed_data.append(item.data)
                else:
                    processed_data.append(item)
            new_df = self._constructor(processed_data)
            return pd.concat([self, new_df], ignore_index=True)  # type: ignore[return-value]

        @property
        def _constructor(self):
            def _c(*args: Any, **kwargs: Any):
                return Table(*args, **kwargs).__finalize__(self)

            return _c

        def __bool__(self) -> bool:
            return not self.empty

        __hash__ = None  # type: ignore[assignment]

        _CONTENT_COLUMNS = frozenset({"text", "content", "output", "summary", "result", "answer", "response"})
        _SYSTEM_COLUMNS = frozenset(
            {
                "timestamp",
                "sender",
                "sender_name",
                "session_id",
                "context_id",
                "flow_id",
                "files",
                "error",
                "edit",
            }
        )

        def smart_column_order(self) -> Table:
            if self.empty:
                return self
            content_cols = [c for c in self.columns if c.lower() in self._CONTENT_COLUMNS]
            system_cols = [c for c in self.columns if c.lower() in self._SYSTEM_COLUMNS or c.startswith("_")]
            regular_cols = [c for c in self.columns if c not in content_cols and c not in system_cols]
            new_order = content_cols + regular_cols + system_cols
            return self[new_order]

        def to_lc_documents(self) -> list[Document]:
            list_of_dicts = self.to_dict(orient="records")
            documents = []
            for row in list_of_dicts:
                data_copy = row.copy()
                text = data_copy.pop(self._text_key, self._default_value)
                if isinstance(text, str):
                    documents.append(Document(page_content=text, metadata=data_copy))
                else:
                    documents.append(Document(page_content=str(text), metadata=data_copy))
            return documents

        def _docs_to_dataframe(self, docs):
            return Table(docs)

        def __eq__(self, other: object) -> bool:
            if self.empty:
                return False
            if isinstance(other, list) and not other:
                return False
            if not isinstance(other, Table | pd.DataFrame):
                return False
            return super().__eq__(other)

        def to_data(self) -> Data:
            dict_list = self.to_dict(orient="records")
            return Data(data={"results": dict_list})

        def to_message(self) -> Message:
            from lfx.schema.message import Message

            processed_df = self.dropna(how="all")
            processed_df = processed_df.replace(r"^\s*$", "", regex=True)
            processed_df = processed_df.replace(r"\n+", "\n", regex=True)
            processed_df = processed_df.replace(r"\|", r"\\|", regex=True)
            processed_df = processed_df.map(lambda x: str(x).replace("\n", "<br/>") if isinstance(x, str) else x)
            return Message(text=processed_df.to_markdown(index=False))

    _real_table_class = Table
    return Table


class _TableMeta(type):
    """Metaclass that makes `Table` / `DataFrame` a lazy proxy for the real class.

    - `Table(...)` instantiates the real pandas-backed class (loads pandas).
    - `isinstance(x, Table)` uses `sys.modules.get("pandas")` — returns False
      without loading pandas when it isn't already loaded.
    - `Table.some_classmethod(...)` forwards to the real class.
    """

    def __call__(cls, *args: Any, **kwargs: Any):  # type: ignore[override]
        return _get_real_table()(*args, **kwargs)

    def __instancecheck__(cls, instance: Any) -> bool:
        _pd = sys.modules.get("pandas")
        return _pd is not None and isinstance(instance, _pd.DataFrame)

    def __subclasscheck__(cls, subclass: type) -> bool:
        _pd = sys.modules.get("pandas")
        return _pd is not None and issubclass(subclass, _pd.DataFrame)

    def __getattr__(cls, name: str) -> Any:
        # Forward class attribute access (e.g. Table.from_dict) to the real class.
        # Skip dunder probes (typing, inspect, copy, pickle, etc. touch many of
        # these during introspection) so we don't force pandas to materialize
        # just because something called get_type_hints() on a DataFrame-annotated
        # function. If real code actually needs a dunder on Table, it can call
        # `Table()` first to materialize.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return getattr(_get_real_table(), name)


class Table(metaclass=_TableMeta):
    """Lazy proxy for the real pandas-backed Table class. See module docstring."""


# Backwards-compatible alias.
DataFrame = Table
