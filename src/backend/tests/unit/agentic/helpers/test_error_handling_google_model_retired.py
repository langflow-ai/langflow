"""Google's "no longer available to new users" 404 must trigger the assistant model fallback.

Reproduced from LE-2310 (1.12.0rc1): the assistant default-resolves
``gemini-2.5-pro`` for Google Generative AI, and Google answers a newly issued
API key with a 404 saying the model is no longer available to new users.
``is_model_unavailable_error`` does not match that phrasing, so the fallback
chain in the assistant streamer never runs and the user gets a terminal
``Model not available`` on the first send — even though the provider offers ten
other callable models.
"""

from langflow.agentic.helpers.error_handling import is_model_unavailable_error

GOOGLE_MODEL_RETIRED_ERROR = (
    "Error building Component Agent:\n\n"
    "Error calling model 'gemini-2.5-pro' (Not Found): 404 Not Found. "
    '{\'message\': \'{\\n  "error": {\\n    "code": 404,\\n    "message": "This model '
    "models/gemini-2.5-pro is no longer available to new users. Please update your code to use "
    'models/gemini-3.1-pro-preview for the latest features and improvements.",\\n    '
    "\"status\": \"NOT_FOUND\"\\n  }\\n}\\n', 'status': 'Not Found'}."
)


class TestGoogleRetiredModelDetection:
    def test_should_flag_model_unavailable_when_google_retires_model_for_new_keys(self):
        assert is_model_unavailable_error(GOOGLE_MODEL_RETIRED_ERROR) is True

    def test_should_flag_model_unavailable_for_any_model_name_google_retires(self):
        error = "This model models/gemini-1.5-pro is no longer available to new users."

        assert is_model_unavailable_error(error) is True

    def test_should_not_flag_auth_errors_as_model_unavailable(self):
        error = "API key not valid. Please pass a valid API key."

        assert is_model_unavailable_error(error) is False

    def test_should_not_flag_quota_errors_as_model_unavailable(self):
        error = "429 Resource has been exhausted (e.g. check quota)."

        assert is_model_unavailable_error(error) is False
