"""A stand-in for the Mailtrap API at the HTTP boundary.

The components call the real ``mailtrap`` SDK.  Only ``requests.Session.request``
is replaced, so each test sees the exact method, URL, query and JSON body the
SDK would send, and no test reaches the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
import requests

MAILTRAP_HOSTS = {"send.api.mailtrap.io", "bulk.api.mailtrap.io", "sandbox.api.mailtrap.io", "mailtrap.io"}


@dataclass
class Call:
    method: str
    url: str
    params: dict[str, Any] | None
    json: Any
    headers: dict[str, str]


class FakeMailtrap:
    def __init__(self) -> None:
        # Each route answers with its responses in order and repeats the last one.
        self.routes: dict[tuple[str, str], list[tuple[int, bytes]]] = {}
        self.calls: list[Call] = []

    def add(self, method: str, url: str, payload: Any = None, *, status: int = 200, text: str | None = None) -> None:
        if text is not None:
            body = text.encode()
        elif payload is not None:
            body = json.dumps(payload).encode()
        else:
            body = b""
        self.routes.setdefault((method, url), []).append((status, body))

    def request(self, session: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
        host = url.split("/")[2]
        assert host in MAILTRAP_HOSTS, f"request to a non-Mailtrap host: {url}"
        self.calls.append(Call(method, url, kwargs.get("params"), kwargs.get("json"), dict(session.headers)))
        if (method, url) not in self.routes:
            msg = f"unexpected request {method} {url}"
            raise AssertionError(msg)
        responses = self.routes[(method, url)]
        status, body = responses.pop(0) if len(responses) > 1 else responses[0]
        response = requests.Response()
        response.status_code = status
        response.url = url
        response._content = body
        return response


@pytest.fixture
def mailtrap_api():
    fake = FakeMailtrap()

    def request(session, method, url, **kwargs):
        return fake.request(session, method, url, **kwargs)

    with patch.object(requests.Session, "request", request):
        yield fake


def _sandbox_message(**overrides: Any) -> dict[str, Any]:
    message = {
        "id": 4242,
        "inbox_id": 77,
        "subject": "Welcome",
        "sent_at": "2026-10-21T10:00:00.000Z",
        "from_email": "hello@acme.com",
        "from_name": "Acme",
        "to_email": "jane@example.com",
        "to_name": "Jane",
        "email_size": 1200,
        "is_read": False,
        "created_at": "2026-10-21T10:00:00.000Z",
        "updated_at": "2026-10-21T10:00:00.000Z",
        "html_body_size": 300,
        "text_body_size": 100,
        "human_size": "1.2 KB",
        "html_path": "/api/accounts/1/inboxes/77/messages/4242/body.html",
        "txt_path": "/api/accounts/1/inboxes/77/messages/4242/body.txt",
        "raw_path": "/api/accounts/1/inboxes/77/messages/4242/body.raw",
        "download_path": "/api/accounts/1/inboxes/77/messages/4242/body.eml",
        "html_source_path": "/api/accounts/1/inboxes/77/messages/4242/body.htmlsource",
        "blacklists_report_info": False,
        "smtp_information": {"ok": True, "data": {"mail_from_addr": "hello@acme.com", "client_ip": "192.0.2.1"}},
    }
    message.update(overrides)
    return message


# Payload builders as fixtures, so test modules never import from conftest:
# several bundles' tests can run in one pytest session.
@pytest.fixture
def sandbox_message():
    return _sandbox_message
