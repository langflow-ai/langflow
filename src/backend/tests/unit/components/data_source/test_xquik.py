from unittest.mock import Mock, patch

import pandas as pd
import pytest
from lfx.components.data_source.xquik import XquikComponent
from lfx.schema import Data, DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestXquikComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return XquikComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "operation": XquikComponent.SEARCH_TWEETS,
            "api_key": "xq_test_key",
            "query": "langflow",
            "tweet_id": "",
            "user_identifier": "",
            "query_type": "Latest",
            "limit": 20,
            "cursor": "",
            "woeid": 1,
            "include_replies": False,
            "include_parent_tweet": False,
            "base_url": "https://xquik.com/api/v1",
            "timeout": 30,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_update_build_config_for_get_tweet(self, component_class):
        component = component_class()
        build_config = {
            "query": {"show": True},
            "tweet_id": {"show": False},
            "user_identifier": {"show": False},
            "query_type": {"show": True},
            "limit": {"show": True},
            "cursor": {"show": True},
            "woeid": {"show": True},
            "include_replies": {"show": True},
            "include_parent_tweet": {"show": True},
        }

        updated = component.update_build_config(build_config, XquikComponent.GET_TWEET, "operation")

        assert not updated["query"]["show"]
        assert updated["tweet_id"]["show"]
        assert not updated["user_identifier"]["show"]
        assert not updated["query_type"]["show"]
        assert not updated["limit"]["show"]
        assert not updated["cursor"]["show"]
        assert not updated["woeid"]["show"]
        assert not updated["include_replies"]["show"]
        assert not updated["include_parent_tweet"]["show"]

    def test_builds_search_tweets_request(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)

        assert component._build_url(XquikComponent.SEARCH_TWEETS) == "https://xquik.com/api/v1/x/tweets/search"
        assert component._build_params(XquikComponent.SEARCH_TWEETS) == {
            "q": "langflow",
            "queryType": "Latest",
            "limit": 20,
        }

    def test_builds_user_tweets_request_with_options(self, component_class, default_kwargs):
        component = component_class(
            **{
                **default_kwargs,
                "operation": XquikComponent.USER_TWEETS,
                "user_identifier": "xquik",
                "cursor": "next-page",
                "include_replies": True,
                "include_parent_tweet": True,
            }
        )

        assert component._build_url(XquikComponent.USER_TWEETS) == "https://xquik.com/api/v1/x/users/xquik/tweets"
        assert component._build_params(XquikComponent.USER_TWEETS) == {
            "includeReplies": True,
            "includeParentTweet": True,
            "cursor": "next-page",
        }

    @patch("lfx.components.data_source.xquik.requests.get")
    def test_run_table_returns_dataframe(self, mock_get, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        response = Mock()
        response.json.return_value = {"tweets": [{"id": "1", "text": "Hello Langflow"}], "has_more": False}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = component.run_table()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert isinstance(result, pd.DataFrame)
        assert result.iloc[0]["id"] == "1"
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["x-api-key"] == "xq_test_key"
        assert kwargs["headers"]["xquik-api-contract"] == "2026-04-29"
        assert kwargs["params"]["q"] == "langflow"

    @patch("lfx.components.data_source.xquik.requests.get")
    def test_run_json_returns_payload(self, mock_get, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        response = Mock()
        response.json.return_value = {"tweets": [{"id": "1"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = component.run_json()

        assert isinstance(result, Data)
        assert result.data["tweets"] == [{"id": "1"}]
        assert result.data["operation"] == XquikComponent.SEARCH_TWEETS

    @patch("lfx.components.data_source.xquik.requests.get")
    def test_run_text_returns_json_lines(self, mock_get, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        response = Mock()
        response.json.return_value = {"users": [{"id": "42", "username": "xquik"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = component.run_text()

        assert isinstance(result, Message)
        assert '"username": "xquik"' in result.text
        assert result.data["users"] == [{"id": "42", "username": "xquik"}]

    def test_missing_query_raises(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "query": ""})

        with pytest.raises(ValueError, match="Query is required"):
            component._build_params(XquikComponent.SEARCH_TWEETS)

    def test_limit_is_bounded(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "limit": 999})

        assert component._build_params(XquikComponent.SEARCH_TWEETS)["limit"] == 200
