import openai
import pytest


def skip_on_openai_quota_error(item: pytest.Item):
    """Skip tests automatically if an OpenAI API insufficient quota error occurs."""
    try:
        item.runtest()
    except openai.RateLimitError as e:
        message = str(e)
        if "insufficient_quota" in message or e.status_code == 429:
            pytest.skip(f"Skipped due to OpenAI insufficient quota error: {message}")
        else:
            raise
