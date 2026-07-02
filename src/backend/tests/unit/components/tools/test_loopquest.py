from unittest.mock import MagicMock, patch

from lfx.components.tools.loopquest import LoopQuestComponent
from lfx.components.tools.loopquest_core import build_task_body, verdict_to_string


def test_loopquest_initialization():
    component = LoopQuestComponent()
    assert component.display_name == "LoopQuest Human Review"
    assert component.name == "LoopQuestHumanReview"
    assert component.icon == "LoopQuest"


def test_build_task_body_defaults():
    body = build_task_body(content="ship it?")
    assert body["module"] == "swiper"
    assert body["mode"] == "gate"
    assert body["payload"] == {"content": "ship it?", "body": "ship it?"}
    assert body["source"] == "langflow"
    assert "timeout_seconds" not in body


def test_build_task_body_grounding_and_gate():
    body = build_task_body(
        content="x",
        module="grounding",
        mode="gate",
        timeout_seconds=3600,
        claim="Flood is covered.",
        source="Policy excludes flood.",
    )
    assert body["payload"] == {
        "content": "x",
        "body": "x",
        "claim": "Flood is covered.",
        "source": "Policy excludes flood.",
    }
    assert body["timeout_seconds"] == 3600
    assert body["on_timeout"] == "escalate"


def test_verdict_to_string():
    assert verdict_to_string({"status": "pending"}) is None
    assert "APPROVED" in verdict_to_string({"status": "reviewed", "verdict": True})
    flagged = verdict_to_string({"status": "reviewed", "verdict": False, "verdict_reason": "PII leak"})
    assert "FLAGGED" in flagged
    assert "PII leak" in flagged
    assert "ESCALATED" in verdict_to_string({"status": "escalated"})


def test_build_tool_returns_named_tool():
    component = LoopQuestComponent()
    component.api_key = "lq_test"
    tool = component.build_tool()
    assert tool.name == "request_human_review"


@patch("lfx.components.tools.loopquest.time.sleep", return_value=None)
@patch("lfx.components.tools.loopquest.httpx")
def test_review_gate_returns_verdict(mock_httpx, _mock_sleep):
    mock_httpx.HTTPError = Exception
    created = MagicMock()
    created.json.return_value = {"id": "t1"}
    polled = MagicMock()
    polled.json.return_value = {"status": "reviewed", "verdict": True}
    mock_httpx.post.return_value = created
    mock_httpx.get.return_value = polled

    component = LoopQuestComponent()
    component.api_key = "lq_test"
    component.game = "swiper"
    component.mode = "gate"
    component.poll_seconds = 1
    component.max_wait_seconds = 10
    component.timeout_seconds = 3600

    result = component._review("send the refund?")
    assert "APPROVED" in result


@patch("lfx.components.tools.loopquest.httpx")
def test_review_monitor_does_not_wait(mock_httpx):
    mock_httpx.HTTPError = Exception
    created = MagicMock()
    created.json.return_value = {"id": "t9"}
    mock_httpx.post.return_value = created

    component = LoopQuestComponent()
    component.api_key = "lq_test"
    component.game = "swiper"
    component.mode = "monitor"
    component.timeout_seconds = 3600
    component.max_wait_seconds = 300
    component.poll_seconds = 5

    result = component._review("fyi only")
    assert "monitor mode" in result
    mock_httpx.get.assert_not_called()
