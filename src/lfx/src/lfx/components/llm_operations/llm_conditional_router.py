from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, HandleInput, MessageInput, MessageTextInput, MultilineInput, Output, TableInput
from lfx.schema.message import Message
from lfx.schema.table import EditMode


class SmartRouterComponent(Component):
    display_name = "Smart Router"
    description = "Routes an input message using LLM-based categorization."
    icon = "route"
    name = "SmartRouter"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._matched_category = None

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
            info="The primary text input for the operation.",
            required=True,
        ),
        TableInput(
            name="routes",
            display_name="Routes",
            info=(
                "Define the categories for routing. Each row should have a route/category name "
                "and optionally a custom output value."
            ),
            table_schema=[
                {
                    "name": "route_category",
                    "display_name": "Route Name",
                    "type": "str",
                    "description": "Name for the route (used for both output name and category matching)",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "route_description",
                    "display_name": "Route Description",
                    "type": "str",
                    "description": "Description of when this route should be used (helps LLM understand the category)",
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "output_value",
                    "display_name": "Route Message (Optional)",
                    "type": "str",
                    "description": (
                        "Optional message to send when this route is matched."
                        "Leave empty to pass through the original input text."
                    ),
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
            ],
            value=[
                {
                    "route_category": "Positive",
                    "route_description": "Positive feedback, satisfaction, or compliments",
                    "output_value": "",
                },
                {
                    "route_category": "Negative",
                    "route_description": "Complaints, issues, or dissatisfaction",
                    "output_value": "",
                },
            ],
            real_time_refresh=True,
            required=True,
        ),
        MessageInput(
            name="message",
            display_name="Override Output",
            info=(
                "Optional override message that will replace both the Input and Output Value "
                "for all routes when filled."
            ),
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="enable_else_output",
            display_name="Include Else Output",
            info="Include an Else output for cases that don't match any route.",
            value=False,
            advanced=True,
        ),
        MultilineInput(
            name="custom_prompt",
            display_name="Additional Instructions",
            info=(
                "Additional instructions for LLM-based categorization. "
                "These will be added to the base prompt. "
                "Use {input_text} for the input text and {routes} for the available categories."
            ),
            advanced=True,
        ),
    ]

    outputs: list[Output] = []

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create a dynamic output for each category in the categories table."""
        if field_name in {"routes", "enable_else_output"}:
            frontend_node["outputs"] = []

            # Get the routes data - either from field_value (if routes field) or from component state
            routes_data = field_value if field_name == "routes" else getattr(self, "routes", [])

            # Add a dynamic output for each category - all using the same method
            for i, row in enumerate(routes_data):
                route_category = row.get("route_category", f"Category {i + 1}")
                frontend_node["outputs"].append(
                    Output(
                        display_name=route_category,
                        name=f"category_{i + 1}_result",
                        method="process_case",
                        group_outputs=True,
                    )
                )
            # Add default output only if enabled
            if field_name == "enable_else_output":
                enable_else = field_value
            else:
                enable_else = getattr(self, "enable_else_output", False)

            if enable_else:
                frontend_node["outputs"].append(
                    Output(display_name="Else", name="default_result", method="default_response", group_outputs=True)
                )
        return frontend_node

    def process_case(self) -> Message:
        """Process all categories using LLM categorization and return message for matching category."""
        # Clear any previous match state
        self._matched_category = None

        # Get categories and input text
        categories = getattr(self, "routes", [])
        input_text = getattr(self, "input_text", "")

        # Find the matching category using LLM-based categorization
        matched_category = None
        llm = getattr(self, "llm", None)

        if llm and categories:
            # Create prompt for categorization
            category_info = []
            for i, category in enumerate(categories):
                cat_name = category.get("route_category", f"Category {i + 1}")
                cat_desc = category.get("route_description", "")
                if cat_desc and cat_desc.strip():
                    category_info.append(f'"{cat_name}": {cat_desc}')
                else:
                    category_info.append(f'"{cat_name}"')

            categories_text = "\n".join([f"- {info}" for info in category_info if info])

            # Create base prompt
            base_prompt = (
                f"You are a text classifier. Given the following text and categories, "
                f"determine which category best matches the text.\n\n"
                f'Text to classify: "{input_text}"\n\n'
                f"Available categories:\n{categories_text}\n\n"
                f"Respond with ONLY the exact category name that best matches the text. "
                f'If none match well, respond with "NONE".\n\n'
                f"Category:"
            )

            # Use custom prompt as additional instructions if provided
            custom_prompt = getattr(self, "custom_prompt", "")
            if custom_prompt and custom_prompt.strip():
                self.status = "Using custom prompt as additional instructions"
                # Format custom prompt with variables
                # For the routes variable, create a simpler format for custom prompt usage
                simple_routes = ", ".join(
                    [f'"{cat.get("route_category", f"Category {i + 1}")}"' for i, cat in enumerate(categories)]
                )
                formatted_custom = custom_prompt.format(input_text=input_text, routes=simple_routes)
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

                # Find matching category based on LLM response
                for i, category in enumerate(categories):
                    route_category = category.get("route_category", "")

                    # Log each comparison attempt
                    self.status = (
                        f"Comparing '{categorization}' with category {i + 1}: route_category='{route_category}'"
                    )

                    # Case-insensitive match
                    if categorization.lower() == route_category.lower():
                        matched_category = i
                        self.status = f"MATCH FOUND! Category {i + 1} matched with '{categorization}'"
                        break

                if matched_category is None:
                    self.status = (
                        f"No match found for '{categorization}'. Available categories: "
                        f"{[category.get('route_category', '') for category in categories]}"
                    )

            except RuntimeError as e:
                self.status = f"Error in LLM categorization: {e!s}"
        else:
            self.status = "No LLM provided for categorization"

        if matched_category is not None:
            # Store the matched category for other outputs to check
            self._matched_category = matched_category

            # Stop all category outputs except the matched one
            for i in range(len(categories)):
                if i != matched_category:
                    self.stop(f"category_{i + 1}_result")

            # Also stop the default output (if it exists)
            enable_else = getattr(self, "enable_else_output", False)
            if enable_else:
                self.stop("default_result")

            route_category = categories[matched_category].get("route_category", f"Category {matched_category + 1}")
            self.status = f"Categorized as {route_category}"

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

            # Check if there's a custom output value for this category
            custom_output = categories[matched_category].get("output_value", "")
            # Treat None, empty string, or whitespace as blank
            if custom_output and str(custom_output).strip() and str(custom_output).strip().lower() != "none":
                # Use custom output value
                return Message(text=str(custom_output))
            # Use input as default output
            return Message(text=input_text)
        # No match found, stop all category outputs
        for i in range(len(categories)):
            self.stop(f"category_{i + 1}_result")

        # Check if else output is enabled
        enable_else = getattr(self, "enable_else_output", False)
        if enable_else:
            # The default_response will handle the else case
            self.stop("process_case")
            return Message(text="")
        # No else output, so no output at all
        self.status = "No match found and Else output is disabled"
        return Message(text="")

    def default_response(self) -> Message:
        """Handle the else case when no conditions match."""
        # Check if else output is enabled
        enable_else = getattr(self, "enable_else_output", False)
        if not enable_else:
            self.status = "Else output is disabled"
            return Message(text="")

        # Clear any previous match state if not already set
        if not hasattr(self, "_matched_category"):
            self._matched_category = None

        categories = getattr(self, "routes", [])
        input_text = getattr(self, "input_text", "")

        # Check if a match was already found in process_case
        if hasattr(self, "_matched_category") and self._matched_category is not None:
            self.status = (
                f"Match already found in process_case (Category {self._matched_category + 1}), "
                "stopping default_response"
            )
            self.stop("default_result")
            return Message(text="")

        # Check if any category matches using LLM categorization
        has_match = False
        llm = getattr(self, "llm", None)

        if llm and categories:
            try:
                # Create prompt for categorization
                category_info = []
                for i, category in enumerate(categories):
                    cat_name = category.get("route_category", f"Category {i + 1}")
                    cat_desc = category.get("route_description", "")
                    if cat_desc and cat_desc.strip():
                        category_info.append(f'"{cat_name}": {cat_desc}')
                    else:
                        category_info.append(f'"{cat_name}"')

                categories_text = "\n".join([f"- {info}" for info in category_info if info])

                # Create base prompt
                base_prompt = (
                    "You are a text classifier. Given the following text and categories, "
                    "determine which category best matches the text.\n\n"
                    f'Text to classify: "{input_text}"\n\n'
                    f"Available categories:\n{categories_text}\n\n"
                    "Respond with ONLY the exact category name that best matches the text. "
                    'If none match well, respond with "NONE".\n\n'
                    "Category:"
                )

                # Use custom prompt as additional instructions if provided
                custom_prompt = getattr(self, "custom_prompt", "")
                if custom_prompt and custom_prompt.strip():
                    self.status = "Using custom prompt as additional instructions (default check)"
                    # Format custom prompt with variables
                    # For the routes variable, create a simpler format for custom prompt usage
                    simple_routes = ", ".join(
                        [f'"{cat.get("route_category", f"Category {i + 1}")}"' for i, cat in enumerate(categories)]
                    )
                    formatted_custom = custom_prompt.format(input_text=input_text, routes=simple_routes)
                    # Combine base prompt with custom instructions
                    prompt = f"{base_prompt}\n\nAdditional Instructions:\n{formatted_custom}"
                else:
                    self.status = "Using default prompt for LLM categorization (default check)"
                    prompt = base_prompt

                # Log the final prompt being sent to LLM for default check
                self.status = f"Default check - Prompt sent to LLM:\n{prompt}"

                # Use the LLM to categorize
                if hasattr(llm, "invoke"):
                    response = llm.invoke(prompt)
                    if hasattr(response, "content"):
                        categorization = response.content.strip().strip('"')
                    else:
                        categorization = str(response).strip().strip('"')
                else:
                    categorization = str(llm(prompt)).strip().strip('"')

                # Log the categorization process for default check
                self.status = f"Default check - LLM response: '{categorization}'"

                # Check if LLM response matches any category
                for i, category in enumerate(categories):
                    route_category = category.get("route_category", "")

                    # Log each comparison attempt
                    self.status = (
                        f"Default check - Comparing '{categorization}' with category {i + 1}: "
                        f"route_category='{route_category}'"
                    )

                    if categorization.lower() == route_category.lower():
                        has_match = True
                        self.status = f"Default check - MATCH FOUND! Category {i + 1} matched with '{categorization}'"
                        break

                if not has_match:
                    self.status = (
                        f"Default check - No match found for '{categorization}'. "
                        f"Available categories: "
                        f"{[category.get('route_category', '') for category in categories]}"
                    )

            except RuntimeError:
                pass  # If there's an error, treat as no match

        if has_match:
            # A case matches, stop this output
            self.stop("default_result")
            return Message(text="")

        # No case matches, check for override output first, then use input as default
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
