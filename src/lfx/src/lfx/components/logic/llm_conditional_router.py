from langflow.custom import Component
from langflow.io import BoolInput, MessageInput, MessageTextInput, Output, HandleInput, TableInput, MultilineInput
from langflow.schema.message import Message
from typing import Any


class LLMConditionalRouterComponent(Component):
    display_name = "Conditional Router"
    description = "Routes an input message to a corresponding output based on LLM-based categorization."
    icon = "equal"
    name = "SmartConditionalRouter"

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
            display_name="Input Text",
            info="The primary text input for the operation.",
             required=True,
        ),
        TableInput(
            name="categories",
            display_name="Categories",
            info="Define the categories for routing. Each row should have an output name, a category, and optionally a custom output value.",
            table_schema=[
                {"name": "label", "display_name": "Output Name", "type": "str", "description": "Name for the output (used for output name)"},
                {"name": "value", "display_name": "Category", "type": "str", "description": "Category to match"},
                {"name": "output_value", "display_name": "Output Value", "type": "str", "description": "Custom message for this category (overrides default output message if filled)", "default": ""},
            ],
            value=[],
            real_time_refresh=True,
            required=True,
        ),
        MessageInput(
            name="message",
            display_name="Default Output Message",
            info="The default message to pass through when no custom output value is specified for a category.",
            required=True,
        ),
        BoolInput(
            name="use_custom_prompt",
            display_name="Use Custom Prompt",
            info="Enable to use a custom prompt for LLM-based categorization.",
            value=False,
            advanced=True,
        ),
        MultilineInput(
            name="custom_prompt",
            display_name="Custom Prompt",
            info="Additional instructions for LLM-based categorization. These will be added to the base prompt. Use {input_text} for the input text and {categories} for the available categories.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Else", name="default_result", method="default_response", group_outputs=True),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create a dynamic output for each category in the categories table."""
        if field_name == "categories":
            frontend_node["outputs"] = []
            
            # Add a dynamic output for each category - all using the same method
            for i, row in enumerate(field_value):
                label = row.get("label", f"Category {i+1}")
                frontend_node["outputs"].append(
                    Output(
                        display_name=label,
                        name=f"category_{i+1}_result",
                        method="process_case",
                        group_outputs=f"True"
                    )
                )
            # Always add a default output
            frontend_node["outputs"].append(
                Output(display_name="Else", name="default_result", method="default_response", group_outputs=True)
            )
        return frontend_node

    def process_case(self) -> Message:
        """Process all categories using LLM categorization and return message for matching category."""
        # Clear any previous match state
        self._matched_category = None
        
        categories = getattr(self, "categories", [])
        input_text = getattr(self, "input_text", "")
        message = getattr(self, "message", Message(text=""))
        
        # Find the matching category using LLM-based categorization
        matched_category = None
        llm = getattr(self, "llm", None)
        
        if llm and categories:
            # Create prompt for categorization
            category_values = [category.get("value", category.get("label", f"Category {i+1}")) for i, category in enumerate(categories)]
            categories_text = ", ".join([f'"{cat}"' for cat in category_values if cat])
            
            # Create base prompt
            base_prompt = f"""You are a text classifier. Given the following text and categories, determine which category best matches the text.

Text to classify: "{input_text}"

Available categories: {categories_text}

Respond with ONLY the exact category name that best matches the text. If none match well, respond with "NONE".

Category:"""

            # Use custom prompt as additional instructions if enabled
            use_custom_prompt = getattr(self, "use_custom_prompt", False)
            custom_prompt = getattr(self, "custom_prompt", "")
            if use_custom_prompt and custom_prompt:
                self.status = "Using custom prompt as additional instructions"
                # Format custom prompt with variables
                formatted_custom = custom_prompt.format(
                    input_text=input_text,
                    categories=categories_text
                )
                # Combine base prompt with custom instructions
                prompt = f"{base_prompt}\n\nAdditional Instructions:\n{formatted_custom}"
            else:
                self.status = "Using default prompt for LLM categorization"
                prompt = base_prompt
            
            # Log the final prompt being sent to LLM
            self.status = f"Prompt sent to LLM:\n{prompt}"
            
            try:
                # Use the LLM to categorize
                if hasattr(llm, 'invoke'):
                    response = llm.invoke(prompt)
                    if hasattr(response, 'content'):
                        categorization = response.content.strip().strip('"')
                    else:
                        categorization = str(response).strip().strip('"')
                else:
                    categorization = str(llm(prompt)).strip().strip('"')
                
                # Log the categorization process
                self.status = f"LLM response: '{categorization}'"
                
                # Find matching category based on LLM response
                for i, category in enumerate(categories):
                    category_value = category.get("value", "")
                    category_label = category.get("label", "")
                    
                    # Log each comparison attempt
                    self.status = f"Comparing '{categorization}' with category {i+1}: value='{category_value}', label='{category_label}'"
                    
                    if (categorization.lower() == category_value.lower() or 
                        categorization.lower() == category_label.lower()):
                        matched_category = i
                        self.status = f"MATCH FOUND! Category {i+1} matched with '{categorization}'"
                        break
                
                if matched_category is None:
                    self.status = f"No match found for '{categorization}'. Available categories: {[(category.get('value', ''), category.get('label', '')) for category in categories]}"
                
            except Exception as e:
                self.status = f"Error in LLM categorization: {str(e)}"
        else:
            self.status = "No LLM provided for categorization"
        
        if matched_category is not None:
            # Store the matched category for other outputs to check
            self._matched_category = matched_category
            
            # Stop all category outputs except the matched one
            for i in range(len(categories)):
                if i != matched_category:
                    self.stop(f"category_{i+1}_result")
            
            # Also stop the default output
            self.stop("default_result")
            
            label = categories[matched_category].get("label", f"Category {matched_category+1}")
            self.status = f"Categorized as {label}"
            
            # Check if there's a custom output value for this category
            custom_output = categories[matched_category].get("output_value", "")
            # Treat None, empty string, or whitespace as blank
            if custom_output and str(custom_output).strip() and str(custom_output).strip().lower() != "none":
                # Use custom output value instead of default message
                return Message(text=str(custom_output))
            else:
                # Use default message
                return message
        else:
            # No match found, stop all category outputs
            for i in range(len(categories)):
                self.stop(f"category_{i+1}_result")
            
            # The default_response will handle the else case
            self.stop("process_case")
            return Message(text="")

    def default_response(self) -> Message:
        """Handle the else case when no conditions match."""
        # Clear any previous match state if not already set
        if not hasattr(self, '_matched_category'):
            self._matched_category = None
            
        categories = getattr(self, "categories", [])
        input_text = getattr(self, "input_text", "")
        message = getattr(self, "message", Message(text=""))
        
        # Check if a match was already found in process_case
        if hasattr(self, '_matched_category') and self._matched_category is not None:
            self.status = f"Match already found in process_case (Category {self._matched_category + 1}), stopping default_response"
            self.stop("default_result")
            return Message(text="")
        
        # Check if any category matches using LLM categorization
        has_match = False
        llm = getattr(self, "llm", None)
        
        if llm and categories:
            try:
                # Create prompt for categorization
                category_values = [category.get("value", category.get("label", f"Category {i+1}")) for i, category in enumerate(categories)]
                categories_text = ", ".join([f'"{cat}"' for cat in category_values if cat])
                
                # Create base prompt
                base_prompt = f"""You are a text classifier. Given the following text and categories, determine which category best matches the text.

Text to classify: "{input_text}"

Available categories: {categories_text}

Respond with ONLY the exact category name that best matches the text. If none match well, respond with "NONE".

Category:"""

                # Use custom prompt as additional instructions if enabled
                use_custom_prompt = getattr(self, "use_custom_prompt", False)
                custom_prompt = getattr(self, "custom_prompt", "")
                if use_custom_prompt and custom_prompt:
                    self.status = "Using custom prompt as additional instructions (default check)"
                    # Format custom prompt with variables
                    formatted_custom = custom_prompt.format(
                        input_text=input_text,
                        categories=categories_text
                    )
                    # Combine base prompt with custom instructions
                    prompt = f"{base_prompt}\n\nAdditional Instructions:\n{formatted_custom}"
                else:
                    self.status = "Using default prompt for LLM categorization (default check)"
                    prompt = base_prompt
                
                # Log the final prompt being sent to LLM for default check
                self.status = f"Default check - Prompt sent to LLM:\n{prompt}"
                
                # Use the LLM to categorize
                if hasattr(llm, 'invoke'):
                    response = llm.invoke(prompt)
                    if hasattr(response, 'content'):
                        categorization = response.content.strip().strip('"')
                    else:
                        categorization = str(response).strip().strip('"')
                else:
                    categorization = str(llm(prompt)).strip().strip('"')
                
                # Log the categorization process for default check
                self.status = f"Default check - LLM response: '{categorization}'"
                
                # Check if LLM response matches any category
                for i, category in enumerate(categories):
                    category_value = category.get("value", "")
                    category_label = category.get("label", "")
                    
                    # Log each comparison attempt
                    self.status = f"Default check - Comparing '{categorization}' with category {i+1}: value='{category_value}', label='{category_label}'"
                    
                    if (categorization.lower() == category_value.lower() or 
                        categorization.lower() == category_label.lower()):
                        has_match = True
                        self.status = f"Default check - MATCH FOUND! Category {i+1} matched with '{categorization}'"
                        break
                
                if not has_match:
                    self.status = f"Default check - No match found for '{categorization}'. Available categories: {[(category.get('value', ''), category.get('label', '')) for category in categories]}"
            
            except Exception:
                pass  # If there's an error, treat as no match
        
        if has_match:
            # A case matches, stop this output
            self.stop("default_result")
            return Message(text="")
        
        # No case matches, return the message
        self.status = "Routed to Else (no match)"
        return message
