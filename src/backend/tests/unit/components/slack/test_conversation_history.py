import pytest
from langflow.components.slack.conversation_history import (
    SlackConversationsHistoryComponent,
)
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


@pytest.fixture
def slack_conversation_history():
    return SlackConversationsHistoryComponent()


def test_deepseek_initialization(slack_conversation_history):
    assert slack_conversation_history.display_name == "Fetch Slack Messages"
    assert (
        slack_conversation_history.description
        == "Fetches a conversation's history of messages and events."
    )
    assert slack_conversation_history.icon == "SlackDirectoryLoader"


def test_get_message_successful_execution(mocker, slack_conversation_history):
    mock_response = {
        "ok": True,
        "messages": [{"text": "Test message 1"}, {"text": "Test message 2"}],
    }

    mock_requests = mocker.patch("requests.request")
    mock_requests.return_value.json.return_value = mock_response

    slack_conversation_history.fetch_messages()

    mock_requests.assert_called_once_with(
        "POST",
        "https://slack.com/api/conversations.history",
        json=mocker.ANY,
        headers=mocker.ANY,
        timeout=mocker.ANY
    )


def test_get_message_channel_slack_error_exception(mocker, slack_conversation_history):
    mock_response = {
        "ok": False,
        "error": "some_slack_error",
    }

    mock_requests = mocker.patch("requests.request")
    mock_requests.return_value.json.return_value = mock_response

    with pytest.raises(ValueError, match="Slack Error: some_slack_error") as err:
        slack_conversation_history.fetch_messages()

    mock_requests.assert_called_once_with(
        "POST",
        "https://slack.com/api/conversations.history",
        json=mocker.ANY,
        headers=mocker.ANY,
        timeout=mocker.ANY
    )


def test_build_slack_response_successful_execution(mocker, slack_conversation_history):
    mock_fetch_messages_response = {
        "ok": True,
        "messages": [{"text": "Test message 1"}, {"text": "Test message 2"}],
    }

    mocker.patch.object(
        slack_conversation_history,
        "fetch_messages",
        return_value=mock_fetch_messages_response,
    )

    slack_response_output = slack_conversation_history.build_slack_response()

    slack_conversation_history.fetch_messages.assert_called_once()

    assert isinstance(slack_response_output, Data)


def test_build_messages_successful_execution(mocker, slack_conversation_history):
    mock_messages = [
        Data(data={"text": "Test message 1"}),
        Data(data={"text": "Test message 2"}),
    ]

    mock_response = mocker.patch.object(slack_conversation_history, "response")
    mock_response.return_value.value.return_value.messages = mock_messages

    slack_response_output = slack_conversation_history.build_messages()

    assert isinstance(slack_response_output, DataFrame)
