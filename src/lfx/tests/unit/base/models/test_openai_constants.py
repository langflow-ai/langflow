from lfx.base.models.openai_constants import OPENAI_MODELS_DETAILED

# Shut down by OpenAI on 2026-10-23, see
# https://developers.openai.com/api/docs/deprecations
SHUTDOWN_2026_10_23 = [
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4.1-nano",
    "o1",
    "o1-pro",
    "o3-mini",
    "o4-mini",
]


def test_models_shut_down_on_2026_10_23_are_deprecated():
    by_name = {metadata["name"]: metadata for metadata in OPENAI_MODELS_DETAILED}
    for name in SHUTDOWN_2026_10_23:
        assert name in by_name, f"{name} should stay known for saved flows"
        assert by_name[name].get("deprecated") is True, f"{name} is shut down but not deprecated"
