import openai
import pytest


def skip_on_openai_quota_error(item):
    """Skip tests automatically if an OpenAI API insufficient quota error occurs."""
    # pytest provides the test function as item.obj
    test_func = item.obj

    # Wrap the test function in a try/except
    def wrapped(*args, **kwargs):
        try:
            return test_func(*args, **kwargs)
        except openai.RateLimitError as e:
            message = str(e)
            if "insufficient_quota" in message or getattr(e, "status_code", None) == 429:
                pytest.skip(f"Skipped due to OpenAI insufficient quota error: {message}")
            else:
                raise

    # Replace the original test with the wrapped one
    item.obj = wrapped
