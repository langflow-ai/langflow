from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool, ToolException
from loguru import logger
from typing_extensions import override

from lfx.base.flow_processing.utils import build_data_from_result_data, format_flow_output_data
from lfx.helpers.flow import build_schema_from_inputs, get_arg_names, get_flow_inputs, run_flow
from lfx.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
    from pydantic.v1 import BaseModel

    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import Vertex


class FlowTool(BaseTool):
    name: str
    description: str
    graph: Graph | None = None
    flow_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    inputs: list[Vertex] = []
    get_final_results_only: bool = True

    @property
    def args(self) -> dict:
        schema = self.get_input_schema()
        return schema.schema()["properties"]

    @override
    def get_input_schema(  # type: ignore[misc]
        self, config: RunnableConfig | None = None
    ) -> type[BaseModel]:
        """The tool's input schema."""
        if self.args_schema is not None:
            return self.args_schema
        if self.graph is not None:
            return build_schema_from_inputs(self.name, get_flow_inputs(self.graph))
        msg = "No input schema available."
        raise ToolException(msg)

    def _run(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Use the tool."""
        args_names = get_arg_names(self.inputs)
        if len(args_names) == len(args):
            kwargs = {arg["arg_name"]: arg_value for arg, arg_value in zip(args_names, args, strict=True)}
        elif len(args_names) != len(args) and len(args) != 0:
            msg = "Number of arguments does not match the number of inputs. Pass keyword arguments instead."
            raise ToolException(msg)
        tweaks = {arg["component_name"]: kwargs[arg["arg_name"]] for arg in args_names}

        run_outputs = run_until_complete(
            run_flow(
                graph=self.graph,
                tweaks={key: {"input_value": value} for key, value in tweaks.items()},
                flow_id=self.flow_id,
                user_id=self.user_id,
                session_id=self.session_id,
            )
        )
        if not run_outputs:
            return "No output"
        run_output = run_outputs[0]

        data = []
        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return format_flow_output_data(data)

    def validate_inputs(self, args_names: list[dict[str, str]], args: Any, kwargs: Any):
        """Validate the inputs."""
        if len(args) > 0 and len(args) != len(args_names):
            msg = "Number of positional arguments does not match the number of inputs. Pass keyword arguments instead."
            raise ToolException(msg)

        if len(args) == len(args_names):
            kwargs = {arg_name["arg_name"]: arg_value for arg_name, arg_value in zip(args_names, args, strict=True)}

        missing_args = [arg["arg_name"] for arg in args_names if arg["arg_name"] not in kwargs]
        if missing_args:
            msg = f"Missing required arguments: {', '.join(missing_args)}"
            raise ToolException(msg)

        return kwargs

    def build_tweaks_dict(self, args, kwargs):
        args_names = get_arg_names(self.inputs)
        kwargs = self.validate_inputs(args_names=args_names, args=args, kwargs=kwargs)
        return {arg["component_name"]: kwargs[arg["arg_name"]] for arg in args_names}

    async def _arun(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Use the tool asynchronously."""
        tweaks = self.build_tweaks_dict(args, kwargs)
        try:
            run_id = self.graph.run_id if hasattr(self, "graph") and self.graph else None
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning("Failed to set run_id")
            run_id = None
        run_outputs = await run_flow(
            tweaks={key: {"input_value": value} for key, value in tweaks.items()},
            flow_id=self.flow_id,
            user_id=self.user_id,
            run_id=run_id,
            session_id=self.session_id,
            graph=self.graph,
        )
        if not run_outputs:
            return "No output"
        run_output = run_outputs[0]

        data = []
        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return format_flow_output_data(data)
