"""Credential validation for the Azure AI Foundry provider bundle.

Invoked lazily by lfx's provider registry via the dotted path
``lfx_azure_ai_foundry.validator:validate_azure_ai_foundry_credentials``
declared in ``extension.json``. Importing this module is cheap and only
happens when credential validation is actually triggered.
"""

from __future__ import annotations

from lfx.log.logger import logger


def validate_azure_ai_foundry_credentials(
    provider: str,  # noqa: ARG001 - part of registry validator contract
    variables: dict[str, str],
    model_name: str | None = None,
) -> None:
    """Validate Azure AI Foundry credentials by constructing and invoking the chat model.

    Returns silently when ``api_key``, ``endpoint``, or ``model_name`` is absent
    (incomplete configuration is not an error at this stage). Raises ``ValueError``
    with an actionable message when the Azure endpoint rejects the credentials or
    when construction of the client itself fails. ``provider`` is part of the
    registry validator contract but is not used here since this callable is only
    registered for Azure AI Foundry.
    """
    api_key = variables.get("AZURE_AI_FOUNDRY_API_KEY")
    endpoint = variables.get("AZURE_AI_FOUNDRY_ENDPOINT")

    if not api_key or not endpoint or not model_name:
        return

    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    try:
        llm = AzureAIOpenAIApiChatModel(
            credential=api_key,
            endpoint=endpoint,
            model=model_name,
            max_tokens=1,
        )
        llm.invoke("test")
    except Exception as exc:
        msg = f"Azure AI Foundry credential validation failed: {exc}"
        logger.error(msg)
        raise ValueError(msg) from exc
