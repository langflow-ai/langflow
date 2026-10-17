"""Credential handling shared by the native Langflow components."""

from typing import Any

from lfx.custom.custom_component.component import Component
from pydantic import SecretStr


def _private_key(value: Any) -> Any:
    return SecretStr(value) if isinstance(value, str) else value


def _private_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(parameters)
    if "api_key" in parameters:
        parameters["api_key"] = _private_key(parameters["api_key"])
    return parameters


class CredentialSafeComponent(Component):
    """Keep runtime credentials private and omit their values from exports.

    Langflow resolves credential globals before provider invocation. A literal
    supplied by a Python caller receives the same SecretStr treatment. Exported
    copies leave the secret input empty so the recipient can select their own
    global secret; a masking string must never become a saved credential.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**_private_parameters(kwargs))

    def set(self, **kwargs: Any):
        result = super().set(**_private_parameters(kwargs))
        if "api_key" in kwargs:
            self._attributes["api_key"] = _private_key(self._attributes.get("api_key"))
        return result

    def set_attributes(self, params: dict) -> None:
        # The host retains this mapping as its parameter configuration.
        if "api_key" in params:
            params["api_key"] = _private_key(params["api_key"])
        super().set_attributes(params)
        # The host unwraps password inputs for legacy provider clients. These
        # components unwrap only inside their public-client invocation boundary.
        if "api_key" in self._attributes:
            self._attributes["api_key"] = _private_key(self._attributes["api_key"])
        if "api_key" in params:
            self._response_cache = None

    def set_input_value(self, name: str, value: Any) -> None:
        value = _private_key(value) if name == "api_key" else value
        super().set_input_value(name, value)
        if name == "api_key":
            self._parameters[name] = value
            self.set_attributes({name: value})
            self._response_cache = None

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "api_key" and name in self.__dict__.get("_inputs", {}):
            self.set_input_value(name, value)
            return
        super().__setattr__(name, _private_key(value) if name == "api_key" else value)

    def to_frontend_node(self) -> dict:
        node = super().to_frontend_node()
        field = node["data"]["node"]["template"].get("api_key")
        if field is not None:
            field["value"] = ""
            field["load_from_db"] = True
        return node
