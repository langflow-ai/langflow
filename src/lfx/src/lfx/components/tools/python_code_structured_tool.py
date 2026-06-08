"""Non-executable compatibility stub for the legacy Python Code Structured tool.

SECURITY (report H1-3754930): this component historically ``exec()``'d the
user-supplied ``tool_code`` template field at flow-build time. Because a flow
can be built without authentication once it is marked PUBLIC
(``/api/v1/build_public_tmp/{flow_id}/flow``), that sink was reachable as an
unauthenticated server-side RCE.

The component is deprecated (``legacy=True``, replaced by
``PythonREPLComponent``). Rather than delete it outright — which would break
saved flows that still reference it — it is kept as a non-executable
compatibility stub for one release/patch cycle: existing flows continue to
load, but the component can no longer run arbitrary code. It will be removed in
a future release.
"""

from langchain_classic.agents import Tool
from langchain_core.tools import StructuredTool, ToolException

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.inputs.inputs import BoolInput, DropdownInput, FieldTypes, HandleInput, MessageTextInput, MultilineInput
from lfx.io import Output

DISABLED_MESSAGE = (
    "The 'Python Code Structured' tool has been disabled for security reasons: it executed "
    "arbitrary Python code, which was remotely exploitable through public flows. Rebuild this "
    "step with the 'Python Interpreter' component (PythonREPLComponent) instead."
)


class PythonCodeStructuredTool(LCToolComponent):
    DEFAULT_KEYS = [
        "code",
        "_type",
        "text_key",
        "tool_code",
        "tool_name",
        "tool_description",
        "return_direct",
        "tool_function",
        "global_variables",
        "_classes",
        "_functions",
    ]
    display_name = "Python Code Structured"
    # NOTE: display_name/description/input strings are intentionally kept identical to the
    # pre-stub component so the i18n locale keys (locales/*.json) do not change. The
    # deprecation is signalled via legacy=True, the replacement below, and the runtime
    # ToolException raised by build_tool.
    description = "structuredtool dataclass code to tool"
    documentation = "https://python.langchain.com/docs/modules/tools/custom_tools/#structuredtool-dataclass"
    name = "PythonCodeStructuredTool"
    icon = "Python"
    field_order = ["name", "description", "tool_code", "return_direct", "tool_function"]
    legacy: bool = True
    replacement = ["processing.PythonREPLComponent"]

    inputs = [
        MultilineInput(
            name="tool_code",
            display_name="Tool Code",
            info="Enter the dataclass code.",
            placeholder="def my_function(args):\n    pass",
            required=True,
            real_time_refresh=True,
            refresh_button=True,
        ),
        MessageTextInput(
            name="tool_name",
            display_name="Tool Name",
            info="Enter the name of the tool.",
            required=True,
        ),
        MessageTextInput(
            name="tool_description",
            display_name="Description",
            info="Enter the description of the tool.",
            required=True,
        ),
        BoolInput(
            name="return_direct",
            display_name="Return Directly",
            info="Should the tool return the function output directly?",
        ),
        DropdownInput(
            name="tool_function",
            display_name="Tool Function",
            info="Select the function for additional expressions.",
            options=[],
            required=True,
            real_time_refresh=True,
            refresh_button=True,
        ),
        HandleInput(
            name="global_variables",
            display_name="Global Variables",
            info="Enter the global variables or Create Data Component.",
            input_types=["Data", "JSON"],
            field_type=FieldTypes.DICT,
            is_list=True,
        ),
        MessageTextInput(name="_classes", display_name="Classes", advanced=True),
        MessageTextInput(name="_functions", display_name="Functions", advanced=True),
    ]

    outputs = [
        Output(display_name="Tool", name="result_tool", method="build_tool"),
    ]

    async def build_tool(self) -> Tool:
        """Return a non-executable placeholder tool.

        The previous implementation ``exec()``'d the ``tool_code`` field, which
        allowed arbitrary code execution at build time (reachable
        unauthenticated through public flows — report H1-3754930). It now
        returns a tool that refuses to run, so saved flows still load but no
        code is executed. Use ``PythonREPLComponent`` instead.
        """

        def _disabled(*_args, **_kwargs) -> str:
            raise ToolException(DISABLED_MESSAGE)

        self.status = DISABLED_MESSAGE
        return StructuredTool.from_function(
            func=_disabled,
            name=self.tool_name or "python_code_structured_tool",
            description=self.tool_description or DISABLED_MESSAGE,
            return_direct=bool(self.return_direct),
        )
