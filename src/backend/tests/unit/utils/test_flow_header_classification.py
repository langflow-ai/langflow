import pytest
from langflow.utils.flow_secrets import is_secret_header_name


@pytest.mark.parametrize(
    "header",
    ["Ocp-Apim-Subscription-Key", "OCP-APIM-SUBSCRIPTION-KEY", "Ocp-ApIm-SubsCription-KeY", "ocpApimSubscriptionKey"],
)
def test_treats_azure_apim_subscription_key_as_a_credential(header: str) -> None:
    assert is_secret_header_name(header)
