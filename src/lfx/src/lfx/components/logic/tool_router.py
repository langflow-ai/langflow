from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, HandleInput, MessageInput, MessageTextInput, MultilineInput, Output
from lfx.schema.message import Message


class ToolRouterComponent(Component):
    display_name = "Tool Router"
    description = "Routes an input message to specific tools using LLM-based categorization."
    icon = "split"
    name = "ToolRouter"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._matched_tool = None

    inputs = [
        HandleInput(
            name="llm",
            display_name="Language Model",
            info="LLM to use for categorization.",
            input_types=["LanguageModel"],
            required=True,
        ),
        MessageTextInput(
            name="input_text",
            display_name="Input",
            info="The primary text input for tool selection.",
            required=True,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=True,
            info="Tools that can be selected based on the input categorization.",
            real_time_refresh=True,
        ),
        MessageInput(
            name="message",
            display_name="Override Output",
            info=("Optional override message that will replace the tool output for all routes when filled."),
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="enable_else_output",
            display_name="Include Else Output",
            info="Include an Else output for cases that don't match any tool.",
            value=False,
            advanced=True,
        ),
        MultilineInput(
            name="custom_prompt",
            display_name="Additional Instructions",
            info=(
                "Additional instructions for LLM-based categorization. "
                "These will be added to the base prompt. "
                "Use {input_text} for the input text and {tools} for the available tools."
            ),
            advanced=True,
        ),
    ]

    outputs: list[Output] = []

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create a dynamic output for each connected tool."""
        # Debug logging
        print(f"DEBUG: update_outputs called with field_name='{field_name}', field_value type: {type(field_value)}")
        
        if field_name in {"tools", "enable_else_output"}:
            frontend_node["outputs"] = []

            # Get the tools data - either from field_value (if tools field) or from component state
            tools_data = field_value if field_name == "tools" else getattr(self, "tools", [])
            print(f"DEBUG: tools_data type: {type(tools_data)}, length: {len(tools_data) if tools_data else 0}")

            # Add a dynamic output for each tool
            if tools_data:
                for i, tool in enumerate(tools_data):
                    tool_name = getattr(tool, "name", f"Tool {i + 1}")
                    print(f"DEBUG: Creating output for tool {i}: {tool_name}")
                    frontend_node["outputs"].append(
                        Output(
                            display_name=tool_name,
                            name=f"tool_{i + 1}_result",
                            method="process_tool",
                            group_outputs=True,
                        ).to_dict()
                    )

            # Add default output only if enabled
            if field_name == "enable_else_output":
                enable_else = field_value
            else:
                enable_else = getattr(self, "enable_else_output", False)

            if enable_else:
                print("DEBUG: Adding Else output")
                frontend_node["outputs"].append(
                    Output(display_name="Else", name="default_result", method="default_response", group_outputs=True).to_dict()
                )
        return frontend_node

    def process_tool(self) -> Message:
        """Process all tools using LLM categorization and execute the matching tool."""
        # Clear any previous match state
        self._matched_tool = None

        tools = getattr(self, "tools", [])
        input_text = getattr(self, "input_text", "")

        # Find the matching tool using LLM-based categorization
        matched_tool_index = None
        llm = getattr(self, "llm", None)

        if llm and tools:
            # Create prompt for categorization
            tool_info = []
            for i, tool in enumerate(tools):
                tool_name = getattr(tool, "name", f"Tool {i + 1}")
                tool_desc = getattr(tool, "description", "")
                if tool_desc and tool_desc.strip():
                    tool_info.append(f'"{tool_name}": {tool_desc}')
                else:
                    tool_info.append(f'"{tool_name}"')

            tools_text = "\n".join([f"- {info}" for info in tool_info if info])

            # Create base prompt
            base_prompt = (
                f"You are a tool classifier. Given the following text and available tools, "
                f"determine which tool best matches the task or question.\n\n"
                f'Input text: "{input_text}"\n\n'
                f"Available tools:\n{tools_text}\n\n"
                f"Respond with ONLY the exact tool name that best matches the input. "
                f'If none match well, respond with "NONE".\n\n'
                f"Tool:"
            )

            # Use custom prompt as additional instructions if provided
            custom_prompt = getattr(self, "custom_prompt", "")
            if custom_prompt and custom_prompt.strip():
                self.status = "Using custom prompt as additional instructions"
                # Format custom prompt with variables
                # For the tools variable, create a simpler format for custom prompt usage
                simple_tools = ", ".join(
                    [f'"{getattr(tool, "name", f"Tool {i + 1}")}"' for i, tool in enumerate(tools)]
                )
                formatted_custom = custom_prompt.format(input_text=input_text, tools=simple_tools)
                # Combine base prompt with custom instructions
                prompt = f"{base_prompt}\n\nAdditional Instructions:\n{formatted_custom}"
            else:
                self.status = "Using default prompt for LLM categorization"
                prompt = base_prompt

            # Log the final prompt being sent to LLM
            self.status = f"Prompt sent to LLM:\n{prompt}"

            try:
                # Use the LLM to categorize
                if hasattr(llm, "invoke"):
                    response = llm.invoke(prompt)
                    if hasattr(response, "content"):
                        categorization = response.content.strip().strip('"')
                    else:
                        categorization = str(response).strip().strip('"')
                else:
                    categorization = str(llm(prompt)).strip().strip('"')

                # Log the categorization process
                self.status = f"LLM response: '{categorization}'"

                # Find matching tool based on LLM response
                for i, tool in enumerate(tools):
                    tool_name = getattr(tool, "name", "")

                    # Log each comparison attempt
                    self.status = f"Comparing '{categorization}' with tool {i + 1}: name='{tool_name}'"

                    if categorization.lower() == tool_name.lower():
                        matched_tool_index = i
                        self.status = f"MATCH FOUND! Tool {i + 1} matched with '{categorization}'"
                        break

                if matched_tool_index is None:
                    self.status = (
                        f"No match found for '{categorization}'. Available tools: "
                        f"{[getattr(tool, 'name', '') for tool in tools]}"
                    )

            except RuntimeError as e:
                self.status = f"Error in LLM categorization: {e!s}"
        else:
            self.status = "No LLM or tools provided for categorization"

        if matched_tool_index is not None:
            # Store the matched tool for other outputs to check
            self._matched_tool = matched_tool_index

            # Stop all tool outputs except the matched one
            for i in range(len(tools)):
                if i != matched_tool_index:
                    self.stop(f"tool_{i + 1}_result")

            # Also stop the default output (if it exists)
            enable_else = getattr(self, "enable_else_output", False)
            if enable_else:
                self.stop("default_result")

            matched_tool = tools[matched_tool_index]
            tool_name = getattr(matched_tool, "name", f"Tool {matched_tool_index + 1}")
            self.status = f"Selected tool: {tool_name}"

            # Check if there's an override output (takes precedence over everything)
            override_output = getattr(self, "message", None)
            if (
                override_output
                and hasattr(override_output, "text")
                and override_output.text
                and str(override_output.text).strip()
            ):
                return Message(text=str(override_output.text))
            if override_output and isinstance(override_output, str) and override_output.strip():
                return Message(text=str(override_output))

            # Execute the matched tool
            try:
                if hasattr(matched_tool, "invoke"):
                    result = matched_tool.invoke(input_text)
                elif hasattr(matched_tool, "run"):
                    result = matched_tool.run(input_text)
                elif callable(matched_tool):
                    result = matched_tool(input_text)
                else:
                    result = f"Tool {tool_name} executed with input: {input_text}"

                # Convert result to string if it's not already
                if not isinstance(result, str):
                    result = str(result)

                return Message(text=result)
            except Exception as e:
                error_msg = f"Error executing tool {tool_name}: {e!s}"
                self.status = error_msg
                return Message(text=error_msg)

        # No match found, stop all tool outputs
        for i in range(len(tools)):
            self.stop(f"tool_{i + 1}_result")

        # Check if else output is enabled
        enable_else = getattr(self, "enable_else_output", False)
        if enable_else:
            # The default_response will handle the else case
            self.stop("process_tool")
            return Message(text="")
        # No else output, so no output at all
        self.status = "No match found and Else output is disabled"
        return Message(text="")

    def default_response(self) -> Message:
        """Handle the else case when no tools match."""
        # Check if else output is enabled
        enable_else = getattr(self, "enable_else_output", False)
        if not enable_else:
            self.status = "Else output is disabled"
            return Message(text="")

        # Clear any previous match state if not already set
        if not hasattr(self, "_matched_tool"):
            self._matched_tool = None

        tools = getattr(self, "tools", [])
        input_text = getattr(self, "input_text", "")

        # Check if a match was already found in process_tool
        if hasattr(self, "_matched_tool") and self._matched_tool is not None:
            self.status = (
                f"Match already found in process_tool (Tool {self._matched_tool + 1}), stopping default_response"
            )
            self.stop("default_result")
            return Message(text="")

        # Check for override output first, then use input as default
        override_output = getattr(self, "message", None)
        if (
            override_output
            and hasattr(override_output, "text")
            and override_output.text
            and str(override_output.text).strip()
        ):
            self.status = "Routed to Else (no match) - using override output"
            return Message(text=str(override_output.text))
        if override_output and isinstance(override_output, str) and override_output.strip():
            self.status = "Routed to Else (no match) - using override output"
            return Message(text=str(override_output))
        self.status = "Routed to Else (no match) - using input as default"
        return Message(text=input_text)
