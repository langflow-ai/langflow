"""Fixed-origin, bounded, credential-safe FastAF transport and output mapping."""

import json
from time import monotonic
from urllib.parse import urlsplit

import httpx
from lfx.custom.custom_component.component import Component
from lfx.schema.data import Data

API_ORIGIN = "https://api.fastaf.co"
TIMEOUT_SECONDS = 120
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MIN_SUCCESS = 200
MAX_SUCCESS = 300


class FastAFError(ValueError):
    """An integration-owned safe message; never includes upstream/request text."""


def header_integer(headers, name):
    value = headers.get(name, "")
    return int(value) if value.isascii() and value.isdigit() else None


def boolean_option(value):
    if value in (None, "", "Default"):
        return None
    if isinstance(value, bool):
        return value
    if value in ("true", "false"):
        return value == "true"
    msg = "Choose Default, true or false for boolean options."
    raise FastAFError(msg)


def integer_option(value, label, minimum=0, maximum=None, step=1):
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except (ValueError, TypeError):
        msg = f"{label} must be an integer."
        raise FastAFError(msg) from None
    if number < minimum or (maximum is not None and number > maximum) or (number - minimum) % step:
        msg = f"{label} is outside the supported range or step."
        raise FastAFError(msg)
    return number


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        msg = f"{label} is required."
        raise FastAFError(msg)
    return value.strip()


def public_url(value):
    value = require_text(value, "Page URL")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
        )
    except ValueError:
        valid = False
    if not valid:
        msg = "Page URL must be a public HTTP(S) URL without embedded credentials."
        raise FastAFError(msg)
    return value


def flat_record(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(flat_record(item, f"{prefix}_{key}" if prefix else str(key)))
        return result
    if isinstance(value, list):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return {prefix or "content": value}


def data_rows(body, keys=()):
    if isinstance(body, dict):
        body = next((body[key] for key in keys if isinstance(body.get(key), list)), body)
    rows = [flat_record(item) for item in body] if isinstance(body, list) else [flat_record(body)]
    columns = list(dict.fromkeys(key for row in rows for key in row))
    return [Data(data={key: row.get(key) for key in columns}) for row in rows]


class FastAFBaseComponent(Component):
    icon = "FastAF"
    documentation = "https://fastaf.co/docs/"
    endpoint = ""
    result_keys = ()

    def localization(self):
        return {"country": self.country, "language": self.language}

    def search_page(self):
        return {
            "query": require_text(self.query, "Search Query"),
            "results": integer_option(self.results, "Maximum Results", 1, 100),
            "page": integer_option(self.page, "Page"),
            **self.localization(),
        }

    def scrape_body(self):
        dynamic = boolean_option(self.dynamic)
        premium = boolean_option(self.premium)
        challenge = boolean_option(self.challenge_mode)
        if challenge and (dynamic or premium or self.proxy_country):
            msg = "Challenge Mode cannot combine with rendering, premium proxies or a proxy country."
            raise FastAFError(msg)
        return {
            "url": public_url(self.url),
            "dynamic": dynamic,
            "premium": premium,
            "country": self.proxy_country,
            "wait": integer_option(self.wait, "Browser Wait", 0, 35000),
            "challenge_mode": challenge,
        }

    def request_body(self):
        raise NotImplementedError

    def _request(self, *, binary=False):
        self.last_request = {"http_status": None, "credits_used": None, "credits_remaining": None}
        credential = self.fastaf_api_key
        key = credential.get_secret_value() if hasattr(credential, "get_secret_value") else credential
        if not isinstance(key, str) or not key.strip() or any(char.isspace() for char in key):
            msg = "FastAF API key is required. Set the FastAF API Key secret input."
            raise FastAFError(msg)
        body = {key: value for key, value in self.request_body().items() if value is not None and value != ""}
        headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "langflow-fastaf-bundle",
        }
        try:
            deadline = monotonic() + TIMEOUT_SECONDS
            with httpx.stream(
                "POST",
                f"{API_ORIGIN}/v1/{self.endpoint}",
                json=body,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
                follow_redirects=False,
                verify=True,
                trust_env=False,
            ) as response:
                self.last_request = {
                    "http_status": response.status_code,
                    "credits_used": header_integer(response.headers, "x-fastaf-credits-used"),
                    "credits_remaining": header_integer(response.headers, "x-fastaf-credits-remaining"),
                }
                if not MIN_SUCCESS <= response.status_code < MAX_SUCCESS:
                    messages = {
                        400: "Check required fields and parameter combinations.",
                        401: "Reconnect with a valid API key.",
                        402: (
                            "Check the credit balance. Free tier: 2 free calls per account "
                            "(after email verification), sign up at fastaf.co."
                        ),
                        403: "Check account verification and status.",
                        429: "Rate or concurrency limit reached; wait before retrying.",
                        502: "The source was unavailable, blocked or returned no usable data.",
                        503: "Service capacity is temporarily unavailable.",
                        504: "The source request timed out.",
                    }
                    detail = messages.get(response.status_code, "Unexpected response; check service availability.")
                    msg = f"FastAF HTTP {response.status_code}. {detail}"
                    raise FastAFError(msg)
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES or monotonic() > deadline:
                        msg = "FastAF response exceeded the size/time limit; credits may already have been consumed."
                        raise FastAFError(msg)
                    chunks.append(chunk)
                content = b"".join(chunks)
                content_type = response.headers.get("content-type", "").split(";")[0]
        except httpx.HTTPError:
            msg = "FastAF could not be reached. Check connectivity; a timeout may already have consumed credits."
            raise FastAFError(msg) from None
        if binary:
            return content, content_type
        text = content.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except ValueError:
            return text

    def error_data(self, message):
        result = Data(data={"error": message, **getattr(self, "last_request", {})})
        self.status = result
        return result

    def fetch_content(self):
        try:
            result = data_rows(self._request(), self.result_keys)
        except FastAFError as error:
            result = [self.error_data(str(error))]
        self.status = result
        return result
