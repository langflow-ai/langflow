from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from lfx.base.models.model_utils import _to_str
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable


def _clean_override(value: Any) -> str | None:
    value = _to_str(value)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _find_matching_option(
    options: list[dict[str, Any]],
    *,
    model_name: str,
    provider: str | None,
) -> dict[str, Any] | None:
    for option in options:
        if option.get("name") != model_name:
            continue
        if provider and option.get("provider") != provider:
            continue
        return deepcopy(option)
    return None


def apply_model_overrides(
    model: Any,
    *,
    model_name: Any = None,
    provider: Any = None,
    user_id: str | None = None,
    get_options: Callable[..., list[dict[str, Any]]] | None = None,
) -> Any:
    """Apply optional scalar overrides to a ModelInput selection.

    ``ModelInput`` stores the rich provider/model object the runtime needs. The
    scalar fields added to the model components are intentionally only an overlay:
    they let global variables choose a model name or provider at run time while
    preserving the selected model as the UI-visible default.
    """
    override_name = _clean_override(model_name)
    override_provider = _clean_override(provider)
    if not override_name and not override_provider:
        return model

    if not isinstance(model, list):
        msg = "Model name/provider overrides require a built-in model selection, not a connected model object."
        raise TypeError(msg)

    selected = deepcopy(model[0]) if model else {}
    selected_name = _clean_override(selected.get("name"))
    selected_provider = _clean_override(selected.get("provider"))

    target_name = override_name or selected_name
    target_provider = override_provider or selected_provider
    if not target_name:
        msg = "A model name is required when using model selection overrides."
        raise ValueError(msg)

    if get_options is not None:
        try:
            if options_match := _find_matching_option(
                get_options(user_id=user_id),
                model_name=target_name,
                provider=target_provider,
            ):
                return [options_match]
        except Exception as exc:  # noqa: BLE001
            # The runtime instantiation helpers still have provider-level
            # fallbacks. Keep model execution available if option refresh fails.
            logger.debug("Could not refresh model options for model override: %s", exc)

    provider_changed = bool(target_provider and target_provider != selected_provider)
    if provider_changed:
        selected = {"metadata": {}}

    selected["name"] = target_name
    if target_provider:
        selected["provider"] = target_provider
        selected["category"] = target_provider

    return [selected]
