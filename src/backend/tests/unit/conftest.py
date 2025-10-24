import openai
import pytest


def pytest_runtest_call(item):
    """Skip tests automatically if an OpenAI API insufficient quota error occurs."""
    try:
        item.runtest()
    except openai.RateLimitError as e:
        message = str(e)
        if "insufficient_quota" in message or "429" in message:
            pytest.skip(f"Skipped due to OpenAI insufficient quota error: {message}")
        else:
            raise
