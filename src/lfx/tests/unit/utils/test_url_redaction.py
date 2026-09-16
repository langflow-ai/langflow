"""A URL on its way into a message must not carry what authenticates to it."""

from lfx.utils.url_redaction import redact_urls_in_text, sanitize_url_for_display

CREDENTIAL_URL = "https://user:hunter2@serving.internal/mcp?api_key=secret"


class TestSanitizeUrlForDisplay:
    def test_should_drop_userinfo_and_query(self):
        assert sanitize_url_for_display(CREDENTIAL_URL) == "https://serving.internal/mcp"

    def test_should_keep_a_non_default_port(self):
        """A target named without its port is a different target."""
        assert sanitize_url_for_display("http://user:pw@host.internal:9411/mcp?k=v") == "http://host.internal:9411/mcp"

    def test_should_leave_a_value_that_is_not_a_url(self):
        assert sanitize_url_for_display("billing-mcp") == "billing-mcp"

    def test_should_leave_a_url_without_a_host(self):
        assert sanitize_url_for_display("file:///tmp/x") == "file:///tmp/x"

    def test_should_keep_the_brackets_of_an_ipv6_host(self):
        """Without them the host and port run together and no longer parse as that address."""
        assert sanitize_url_for_display("http://user:pw@[::1]:8080/mcp?k=v") == "http://[::1]:8080/mcp"

    def test_should_drop_userinfo_when_the_port_is_unparseable(self):
        """A malformed port must not stop the credential from being stripped."""
        assert sanitize_url_for_display("https://user:hunter2@host.internal:99999/mcp?k=v") == (
            "https://host.internal:99999/mcp"
        )
        assert sanitize_url_for_display("https://user:hunter2@host.internal:abc/mcp") == (
            "https://host.internal:abc/mcp"
        )

    def test_should_drop_userinfo_when_urlparse_itself_rejects_the_url(self):
        """An unterminated IPv6 literal makes urlparse raise before userinfo is split out."""
        assert sanitize_url_for_display("https://user:hunter2@[::1/mcp") == "https://[::1/mcp"

    def test_should_drop_the_query_when_urlparse_itself_rejects_the_url(self):
        assert sanitize_url_for_display("https://[::1/mcp?api_key=secret") == "https://[::1/mcp"

    def test_should_leave_non_url_text_alone_when_urlparse_raises(self):
        assert sanitize_url_for_display("not-a-url-at-all") == "not-a-url-at-all"


class TestRedactUrlsInText:
    def test_should_redact_a_url_embedded_in_a_sentence(self):
        text = f"Client error '401 Unauthorized' for url '{CREDENTIAL_URL}'"

        redacted = redact_urls_in_text(text)

        assert "hunter2" not in redacted
        assert "secret" not in redacted
        assert "serving.internal" in redacted

    def test_should_redact_every_url_in_a_multiline_traceback(self):
        text = (
            "Traceback (most recent call last):\n"
            f"  httpx.HTTPStatusError: Client error for url '{CREDENTIAL_URL}'\n"
            "  during handling of\n"
            "  httpx.ConnectError: failed to reach http://admin:pw@other.internal:8080/x?token=t\n"
        )

        redacted = redact_urls_in_text(text)

        assert "hunter2" not in redacted
        assert "secret" not in redacted
        assert "pw@" not in redacted
        assert "token=t" not in redacted

    def test_should_redact_a_url_whose_port_is_unparseable(self):
        """Redaction runs while an error is being reported; it must not raise its own."""
        text = "httpx.ConnectError: failed to reach https://admin:hunter2@other.internal:99999/x?token=t"

        redacted = redact_urls_in_text(text)

        assert "hunter2" not in redacted
        assert "token=t" not in redacted
        assert "other.internal" in redacted

    def test_should_leave_text_without_urls_alone(self):
        text = "unhandled errors in a TaskGroup (1 sub-exception)"

        assert redact_urls_in_text(text) == text

    def test_should_redact_a_url_urlparse_itself_rejects(self):
        """Redaction must not hand back the raw, credential-bearing text it failed to parse."""
        text = "MCP connection failed: https://user:hunter2@[::1/mcp"

        redacted = redact_urls_in_text(text)

        assert "hunter2" not in redacted
        assert "[::1" in redacted
