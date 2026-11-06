"""Unit tests for the Sequenzy components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real URLs, headers, payloads and error handling of the client without reaching
the Sequenzy API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.sequenzy.sequenzy_campaigns import SequenzyListCampaignsComponent
from lfx_bundles.sequenzy.sequenzy_common import API_BASE_URL
from lfx_bundles.sequenzy.sequenzy_event import SequenzyTriggerEventComponent
from lfx_bundles.sequenzy.sequenzy_send_email import SequenzySendEmailComponent
from lfx_bundles.sequenzy.sequenzy_subscriber import SequenzyAddSubscriberComponent, SequenzyGetSubscriberComponent
from lfx_bundles.sequenzy.sequenzy_tag import REMOVE_TAG, SequenzyTagSubscriberComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-sequenzy-api-key-placeholder"  # pragma: allowlist secret

ALL_COMPONENTS = [
    SequenzyAddSubscriberComponent,
    SequenzyGetSubscriberComponent,
    SequenzyListCampaignsComponent,
    SequenzySendEmailComponent,
    SequenzyTagSubscriberComponent,
    SequenzyTriggerEventComponent,
]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _component(component_class: type[Component], **values) -> Component:
    component = component_class()
    component.set(**{"api_key": API_KEY, **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Sequenzy"
    assert component.documentation.startswith("https://docs.sequenzy.com/")
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True


@pytest.mark.unit
class TestSharedRequest:
    def test_missing_api_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(SequenzyGetSubscriberComponent, api_key="  ", email="ada@example.com").get_subscriber()

        request.assert_not_called()
        assert data.data["error"] == "Enter a Sequenzy API key."

    def test_api_key_is_sent_as_bearer_token(self) -> None:
        body = {"success": True, "subscriber": {"email": "ada@example.com"}}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            component = _component(SequenzyGetSubscriberComponent, api_key=f"  {API_KEY}  ", email="ada@example.com")
            component.get_subscriber()

        assert request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"

    def test_auth_error_is_returned_and_key_is_redacted(self) -> None:
        body = {"success": False, "error": f"Invalid API key {API_KEY}", "code": "UNAUTHORIZED"}
        with patch("httpx.Client.request", return_value=_response(401, json_body=body)):
            data = _component(SequenzyGetSubscriberComponent, email="ada@example.com").get_subscriber()

        error = data.data["error"]
        assert error.startswith("Sequenzy rejected the API key (401): Invalid API key")
        assert API_KEY not in error

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        body = {"error": "x" * 290 + API_KEY}
        with patch("httpx.Client.request", return_value=_response(500, json_body=body)):
            data = _component(SequenzyGetSubscriberComponent, email="ada@example.com").get_subscriber()

        assert API_KEY[:10] not in data.data["error"]

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            data = _component(SequenzyGetSubscriberComponent, email="ada@example.com").get_subscriber()

        assert "not JSON" in data.data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _component(SequenzyGetSubscriberComponent, email="ada@example.com", timeout=2.5).get_subscriber()

        assert data.data["error"] == "Sequenzy request timed out after 2.5 seconds."

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            data = _component(SequenzyGetSubscriberComponent, email="ada@example.com").get_subscriber()

        assert data.data["error"].startswith("Could not reach the Sequenzy API: ConnectError")


@pytest.mark.unit
class TestSubscribers:
    def test_add_subscriber_sends_fields_tags_and_attributes(self) -> None:
        body = {"success": True, "subscriber": {"email": "ada@example.com"}}
        component = _component(
            SequenzyAddSubscriberComponent,
            email=" ada@example.com ",
            first_name="Ada",
            tags="newsletter, trial,",
            custom_attributes='{"plan": "pro"}',
        )
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            data = component.add_subscriber()

        method, url = request.call_args.args
        assert method == "POST"
        assert url == f"{API_BASE_URL}/subscribers"
        assert request.call_args.kwargs["json"] == {
            "email": "ada@example.com",
            "duplicateStrategy": "overwrite",
            "firstName": "Ada",
            "tags": ["newsletter", "trial"],
            "customAttributes": {"plan": "pro"},
        }
        assert data.data["subscriber"] == body["subscriber"]
        assert data.text == "Saved subscriber ada@example.com."

    def test_add_subscriber_accepts_a_dict_of_attributes(self) -> None:
        component = _component(
            SequenzyAddSubscriberComponent,
            email="ada@example.com",
            custom_attributes={"plan": "pro"},
            duplicate_strategy="merge",
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            component.add_subscriber()

        sent = request.call_args.kwargs["json"]
        assert sent["customAttributes"] == {"plan": "pro"}
        assert sent["duplicateStrategy"] == "merge"

    @pytest.mark.parametrize("attributes", ["not json", "[1, 2]"])
    def test_invalid_attributes_make_no_request(self, attributes: str) -> None:
        component = _component(SequenzyAddSubscriberComponent, email="ada@example.com", custom_attributes=attributes)
        with patch("httpx.Client.request") as request:
            data = component.add_subscriber()

        request.assert_not_called()
        assert "Custom Attributes must be a JSON object" in data.data["error"]

    def test_add_subscriber_requires_an_email(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(SequenzyAddSubscriberComponent, email=" ").add_subscriber()

        request.assert_not_called()
        assert data.data["error"] == "Enter the subscriber's email address."

    def test_get_subscriber_escapes_the_email_in_the_path(self) -> None:
        subscriber = {"email": "ada+test@example.com", "status": "active", "tags": ["vip"]}
        with patch(
            "httpx.Client.request", return_value=_response(json_body={"success": True, "subscriber": subscriber})
        ) as request:
            data = _component(SequenzyGetSubscriberComponent, email="ada+test@example.com").get_subscriber()

        method, url = request.call_args.args
        assert method == "GET"
        assert url == f"{API_BASE_URL}/subscribers/ada%2Btest@example.com"
        assert data.data["status"] == "active"
        assert data.data["tags"] == ["vip"]

    def test_unknown_subscriber_is_an_error(self) -> None:
        body = {"success": False, "error": "Subscriber not found", "code": "NOT_FOUND"}
        with patch("httpx.Client.request", return_value=_response(404, json_body=body)):
            data = _component(SequenzyGetSubscriberComponent, email="nobody@example.com").get_subscriber()

        assert data.data["error"] == "Sequenzy could not find the requested resource (404): Subscriber not found"


@pytest.mark.unit
class TestTagsAndEvents:
    def test_add_tag(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            data = _component(SequenzyTagSubscriberComponent, email="ada@example.com", tag="premium").update_tag()

        assert request.call_args.args == ("POST", f"{API_BASE_URL}/subscribers/tags")
        assert request.call_args.kwargs["json"] == {"email": "ada@example.com", "tag": "premium"}
        assert data.text == "Added tag premium for ada@example.com."

    def test_remove_tag(self) -> None:
        component = _component(SequenzyTagSubscriberComponent, action=REMOVE_TAG, email="ada@example.com", tag="trial")
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            component.update_tag()

        assert request.call_args.args == ("POST", f"{API_BASE_URL}/subscribers/tags/remove")
        assert request.call_args.kwargs["json"] == {"email": "ada@example.com", "tag": "trial"}

    def test_tag_requires_email_and_tag(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(SequenzyTagSubscriberComponent, email="ada@example.com", tag=" ").update_tag()

        request.assert_not_called()
        assert "a tag" in data.data["error"]

    def test_trigger_event_with_properties_and_event_id(self) -> None:
        component = _component(
            SequenzyTriggerEventComponent,
            email="ada@example.com",
            event="purchase.completed",
            properties='{"amount": 9900, "currency": "USD"}',
            event_id="order_123",
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            data = component.trigger_event()

        assert request.call_args.args == ("POST", f"{API_BASE_URL}/subscribers/events")
        assert request.call_args.kwargs["json"] == {
            "email": "ada@example.com",
            "event": "purchase.completed",
            "eventId": "order_123",
            "properties": {"amount": 9900, "currency": "USD"},
        }
        assert data.text == "Triggered purchase.completed for ada@example.com."

    def test_invalid_event_properties_make_no_request(self) -> None:
        component = _component(
            SequenzyTriggerEventComponent, email="ada@example.com", event="signup", properties="{oops"
        )
        with patch("httpx.Client.request") as request:
            data = component.trigger_event()

        request.assert_not_called()
        assert "Event Properties must be a JSON object" in data.data["error"]


@pytest.mark.unit
class TestSendEmail:
    def test_send_template_with_variables_and_idempotency_key(self) -> None:
        component = _component(
            SequenzySendEmailComponent,
            to="ada@example.com",
            slug="welcome-email",
            subject="ignored when a slug is set",
            template_variables='{"name": "Ada"}',
            idempotency_key="signup-ada",
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            data = component.send_email()

        assert request.call_args.args == ("POST", f"{API_BASE_URL}/transactional/send")
        assert request.call_args.kwargs["json"] == {
            "to": "ada@example.com",
            "slug": "welcome-email",
            "variables": {"name": "Ada"},
        }
        assert request.call_args.kwargs["headers"]["Idempotency-Key"] == "signup-ada"
        assert data.text == "Sent email to ada@example.com."

    def test_send_direct_content(self) -> None:
        component = _component(
            SequenzySendEmailComponent, to="ada@example.com", subject="Hello", body="<p>Welcome aboard.</p>"
        )
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})) as request:
            component.send_email()

        assert request.call_args.kwargs["json"] == {
            "to": "ada@example.com",
            "subject": "Hello",
            "body": "<p>Welcome aboard.</p>",
        }
        assert "Idempotency-Key" not in request.call_args.kwargs["headers"]

    @pytest.mark.parametrize("values", [{"subject": "Hello"}, {"body": "<p>Hi</p>"}, {}])
    def test_needs_a_slug_or_subject_and_body(self, values: dict[str, str]) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(SequenzySendEmailComponent, to="ada@example.com", **values).send_email()

        request.assert_not_called()
        assert data.data["error"] == "Enter a template slug, or both a subject and an HTML body."

    def test_validation_error_is_returned(self) -> None:
        body = {"success": False, "error": "Template not found", "code": "NOT_FOUND"}
        with patch("httpx.Client.request", return_value=_response(400, json_body=body)):
            data = _component(SequenzySendEmailComponent, to="ada@example.com", slug="missing").send_email()

        assert data.data["error"] == "Sequenzy API error (400): Template not found"


@pytest.mark.unit
class TestListCampaigns:
    CAMPAIGNS = [
        {"id": "cmp_1", "name": "October launch", "subject": "We shipped", "status": "sent"},
        {"id": "cmp_2", "name": "", "subject": "Draft subject", "status": "draft"},
    ]

    def test_lists_campaigns_as_a_table(self) -> None:
        body = {"success": True, "campaigns": self.CAMPAIGNS, "pagination": {"limit": 20, "offset": 0}}
        with patch("httpx.Client.request", return_value=_response(json_body=body)) as request:
            frame = _component(SequenzyListCampaignsComponent).list_campaigns_dataframe()

        assert request.call_args.args == ("GET", f"{API_BASE_URL}/campaigns")
        assert request.call_args.kwargs["params"] == {"limit": 20}
        assert list(frame["id"]) == ["cmp_1", "cmp_2"]

    def test_status_filter_and_limit_clamp(self) -> None:
        component = _component(SequenzyListCampaignsComponent, campaign_status="sent", limit=500)
        with patch("httpx.Client.request", return_value=_response(json_body={"campaigns": []})) as request:
            component.list_campaigns()

        assert request.call_args.kwargs["params"] == {"limit": 100, "status": "sent"}

    def test_text_falls_back_to_the_subject(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"campaigns": self.CAMPAIGNS})):
            data = _component(SequenzyListCampaignsComponent).list_campaigns()

        assert [item.text for item in data] == ["October launch", "Draft subject"]

    def test_missing_campaigns_list_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(json_body={"success": True})):
            data = _component(SequenzyListCampaignsComponent).list_campaigns()

        assert "without a campaigns list" in data[0].data["error"]
