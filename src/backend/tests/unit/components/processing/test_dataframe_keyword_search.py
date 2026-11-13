import pandas as pd
import pytest
from lfx.components.processing.dataframe_keyword_search import DataFrameKeywordSearch
from lfx.schema.dataframe import DataFrame


def _search(keywords, *, match_type: str = "any", number_candidates: int = 10) -> pd.DataFrame:
    component = DataFrameKeywordSearch()
    component.set_attributes(
        {
            "dataframe": DataFrame(
                pd.DataFrame(
                    {
                        "file_path": ["agent.py", "chat_input.py", "openai.py"],
                        "text": ["class Agent: tools", "class ChatInput: message", "class OpenAIModel: tools"],
                    }
                )
            ),
            "column": "text",
            "keywords": keywords,
            "match_type": match_type,
            "case_sensitive": False,
            "number_candidates": number_candidates,
        }
    )
    return component.search()


def test_any_returns_rows_with_at_least_one_keyword() -> None:
    assert list(_search(["agent", "openai"])["file_path"]) == ["agent.py", "openai.py"]


def test_all_returns_rows_with_every_keyword() -> None:
    assert list(_search(["class", "tools", "agent"], match_type="all")["file_path"]) == ["agent.py"]


def test_coverage_ranks_rows_by_the_share_of_keywords_found() -> None:
    result = _search(["tools", "openai"], match_type="coverage")
    assert list(result["file_path"]) == ["openai.py", "agent.py"]


def test_blank_keywords_do_not_match_every_row() -> None:
    assert list(_search(["agent", "  "])["file_path"]) == ["agent.py"]


def test_no_usable_keyword_still_returns_at_most_the_candidate_limit() -> None:
    assert len(_search([], number_candidates=2)) == 2


def test_an_unknown_match_type_is_refused() -> None:
    with pytest.raises(ValueError, match="Match Type"):
        _search(["agent"], match_type="or")
