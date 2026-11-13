"""Preserve a LangChain tool's execution contract behind a runtime policy check."""

from __future__ import annotations

from inspect import signature
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun  # noqa: TC002
from langchain_core.runnables import RunnableConfig  # noqa: TC002
from langchain_core.tools import BaseTool
from langchain_core.tools.base import _get_runnable_config_param
from pydantic import PrivateAttr
from typing_extensions import override

from lfx.services.auth.utils import run_sync_auth_validation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic import BaseModel


class PolicyCheckedTool(BaseTool):
    """Apply one policy check before invoking the original tool exactly once."""

    _original: BaseTool = PrivateAttr()
    _validate: Callable[[], Awaitable[None]] = PrivateAttr()

    def __init__(self, original: BaseTool, validate: Callable[[], Awaitable[None]]) -> None:
        super().__init__(
            name=original.name,
            description=original.description,
            args_schema=original.args_schema,
            return_direct=original.return_direct,
            verbose=original.verbose,
            callbacks=original.callbacks,
            tags=list(original.tags or []),
            metadata=dict(original.metadata or {}),
            handle_tool_error=original.handle_tool_error,
            handle_validation_error=original.handle_validation_error,
            response_format=original.response_format,
        )
        self._original = original
        self._validate = validate

    def with_policy(self, validate: Callable[[], Awaitable[None]]) -> PolicyCheckedTool:
        updated = self.model_copy()
        updated.set_policy(validate)
        return updated

    def set_policy(self, validate: Callable[[], Awaitable[None]]) -> None:
        self._validate = validate

    @override
    def get_input_schema(self, config: RunnableConfig | None = None) -> type[BaseModel]:
        return self._original.get_input_schema(config)

    @override
    def _to_args_and_kwargs(
        self, tool_input: str | dict[str, Any], tool_call_id: str | None
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        return self._original._to_args_and_kwargs(tool_input, tool_call_id)  # noqa: SLF001

    @staticmethod
    def _injected_kwargs(
        method: Callable[..., Any],
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | AsyncCallbackManagerForToolRun | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if "run_manager" in signature(method).parameters:
            kwargs["run_manager"] = run_manager
        if config_param := _get_runnable_config_param(method):
            kwargs[config_param] = config
        return kwargs

    @override
    def _run(
        self, *args: Any, config: RunnableConfig, run_manager: CallbackManagerForToolRun | None = None, **kwargs: Any
    ) -> Any:
        run_sync_auth_validation(self._validate)
        method = self._original._run  # noqa: SLF001
        kwargs.update(self._injected_kwargs(method, config, run_manager))
        return method(*args, **kwargs)

    @override
    async def _arun(
        self,
        *args: Any,
        config: RunnableConfig,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        await self._validate()
        method = self._original._arun  # noqa: SLF001
        signature_method = self._original._run if type(self._original)._arun is BaseTool._arun else method  # noqa: SLF001
        kwargs.update(self._injected_kwargs(signature_method, config, run_manager))
        return await method(*args, **kwargs)
