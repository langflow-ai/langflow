from unittest.mock import Mock, patch

import pandas as pd
import pytest
import requests
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

    @pytest.mark.parametrize(
        ("operation", "updates", "expected_url", "expected_params"),
        [
            (
                XquikComponent.GET_TWEET,
                {"tweet_id": "123"},
                "https://xquik.com/api/v1/x/tweets/123",
                {},
            ),
            (
                XquikComponent.GET_USER,
                {"user_identifier": "xquik"},
                "https://xquik.com/api/v1/x/users/xquik",
                {},
            ),
            (
                XquikComponent.SEARCH_USERS,
                {"query": "langflow", "cursor": "user-next"},
                "https://xquik.com/api/v1/x/users/search",
                {"q": "langflow", "cursor": "user-next"},
            ),
            (
                XquikComponent.TRENDS,
                {"woeid": 1, "limit": 99},
                "https://xquik.com/api/v1/trends",
                {"woeid": 1, "count": 50},
            ),
        ],
    )
    def test_builds_remaining_operation_requests(
        self,
        component_class,
        default_kwargs,
        operation,
        updates,
        expected_url,
        expected_params,
    ):
        component = component_class(**{**default_kwargs, "operation": operation, **updates})

        assert component._build_url(operation) == expected_url
        assert component._build_params(operation) == expected_params

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
        assert component.status == "Returned 1 record(s)."

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

    @patch("lfx.components.data_source.xquik.requests.get")
    def test_request_exception_returns_error_payload(self, mock_get, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        mock_get.side_effect = requests.Timeout("request timed out")

        result = component.run_json()

        assert result.data["operation"] == XquikComponent.SEARCH_TWEETS
        assert result.data["url"] == "https://xquik.com/api/v1/x/tweets/search"
        assert result.data["error"] == "Xquik request failed: request timed out"
        assert component.status == "Xquik request failed: request timed out"

    @patch("lfx.components.data_source.xquik.requests.get")
    def test_non_json_response_returns_text_payload(self, mock_get, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        response = Mock()
        response.json.side_effect = ValueError("not json")
        response.raise_for_status.return_value = None
        response.text = "plain response"
        mock_get.return_value = response

        result = component.run_json()

        assert result.data == {
            "text": "plain response",
            "operation": XquikComponent.SEARCH_TWEETS,
            "url": "https://xquik.com/api/v1/x/tweets/search",
        }

    def test_missing_api_key_raises(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "api_key": ""})

        with pytest.raises(ValueError, match="Xquik API key is required"):
            component._api_key_value()

    def test_missing_query_raises(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "query": ""})

        with pytest.raises(ValueError, match="Query is required"):
            component._build_params(XquikComponent.SEARCH_TWEETS)

    def test_limit_is_bounded(self, component_class, default_kwargs):
        component = component_class(**{**default_kwargs, "limit": 999})

        assert component._build_params(XquikComponent.SEARCH_TWEETS)["limit"] == 200
