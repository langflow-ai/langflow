import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.schema.message import Message
from lfx.template.field.base import Output

from .serpkite_search import _http_error_message

API_BASE = "https://api.serpkite.com/v1"
# Display name -> endpoint. Answers take seconds (Brave) to under a minute.
ASSISTANTS = {
    "ChatGPT": "chatgpt",
    "Gemini": "gemini",
    "Copilot Search": "copilot",
    "Google AI Mode": "ai_mode",
    "Brave AI": "brave_ai",
}
DEFAULT_ASSISTANT = "ChatGPT"
# The API answers within 90 seconds; leave room for the response.
REQUEST_TIMEOUT = 120
MAX_PROMPT = 4000
MAX_SOURCES = 20
NO_ANSWER = "The assistant returned no answer for this prompt (not billed). Try rephrasing it or another assistant."


class SerpKiteAssistantComponent(Component):
    """Ask a public AI assistant through SerpKite and return its answer with sources."""

    display_name = "SerpKite AI Assistant"
    description = (
        "Ask ChatGPT, Gemini, Copilot Search, Google AI Mode or Brave AI as a logged-out visitor "
        "and get the answer with the sources it cited."
    )
    documentation = "https://serpkite.com/docs/ai-assistants"
    icon = "bot"

    inputs = [
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            info="The question to ask the assistant (up to 4,000 characters).",
            tool_mode=True,
        ),
        DropdownInput(
            name="assistant",
            display_name="Assistant",
            options=list(ASSISTANTS),
            value=DEFAULT_ASSISTANT,
            info="Which AI assistant to ask. Brave AI answers in seconds; the others take up to a minute.",
        ),
        SecretStrInput(
            name="serpkite_api_key",
            display_name="SerpKite Key",
            required=True,
            info="Your SerpKite key. Get one at https://app.serpkite.com/keys.",
            password=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            required=False,
            advanced=True,
            info="Ask from this country, for example 'us' or 'de'. Answers, prices and shops follow it.",
        ),
    ]

    outputs = [
        # Also the tool name in tool mode; specific so it can't clash with other tools.
        Output(display_name="Answer", name="answer", method="serpkite_ask_assistant"),
    ]

    def _endpoint(self) -> str:
        name = self.assistant or DEFAULT_ASSISTANT
        if name not in ASSISTANTS:
            msg = f"Unknown assistant {name!r}. Choose one of: {', '.join(ASSISTANTS)}."
            raise ValueError(msg)
        return f"{API_BASE}/{ASSISTANTS[name]}"

    def _request_body(self) -> dict:
        prompt = (self.prompt or "").strip()
        if not prompt:
            msg = "Prompt is required."
            raise ValueError(msg)
        if len(prompt) > MAX_PROMPT:
            msg = f"Prompt is longer than {MAX_PROMPT} characters."
            raise ValueError(msg)
        body: dict = {"prompt": prompt}
        country = getattr(self, "country", None)
        if isinstance(country, str) and country.strip():
            body["country"] = country.strip()
        return body

    async def _ask(self) -> dict:
        if not self.serpkite_api_key:
            msg = "SerpKite key is required. Set the SerpKite Key input."
            raise ValueError(msg)
        headers = {
            "Authorization": f"Bearer {self.serpkite_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "langflow-serpkite-bundle",
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(self._endpoint(), json=self._request_body(), headers=headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _format_answer(payload: dict) -> str:
        answer = payload.get("markdown") or payload.get("text") or ""
        if not answer.strip():
            # Empty answers are not billed; say so instead of returning nothing.
            return NO_ANSWER
        sources = [s for s in payload.get("sources") or [] if isinstance(s, dict) and s.get("link")]
        if not sources:
            return answer
        lines = [answer, "", "Sources:"]
        for i, source in enumerate(sources[:MAX_SOURCES], start=1):
            title = source.get("title") or source["link"]
            lines.append(f"{source.get('position') or i}. [{title}]({source['link']})")
        return "\n".join(lines)

    async def serpkite_ask_assistant(self) -> Message:
        """Ask the selected assistant and return its answer (Markdown) with cited sources."""
        try:
            payload = await self._ask()
        except httpx.HTTPStatusError as e:
            text = _http_error_message(e)
        except (httpx.HTTPError, ValueError) as e:
            text = f"SerpKite error: {e}"
        else:
            if isinstance(payload, dict):
                text = self._format_answer(payload)
            else:
                text = "SerpKite returned an unexpected response (expected a JSON object)."
        self.status = text
        return Message(text=text)
