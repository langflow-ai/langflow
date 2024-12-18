**Guidelines for Creating Langflow Components**:

1. **Component Structure**:
   - **Imports**:
     - Use `from langflow.custom import Component` to import the base `Component` class.
     - Import necessary modules from `langflow` and other required libraries.
   - **Class Definition**:
     - Define the component class that inherits from `Component` or another appropriate base class.
   - **Metadata**:
     - `display_name`: A human-readable name for the component.
     - `description`: A detailed description of what the component does.
     - `icon`: An icon representing the component in the Langflow interface.
     - `name`: The unique identifier for the component.
   - **Inputs**:
     - Define the component's input fields using the appropriate input types from `langflow.io`.
     - Use clear `display_name` and `info` descriptions for each input.
     - Group related inputs together (e.g., search parameters, pagination).
     - Only set `required=True` for essential fields (like API credentials).
     - Provide default values for nullable or optional fields.
     - Mark less commonly used inputs as `advanced=True`.
     - For numerical inputs requiring `tool_mode`, use `MessageTextInput` and handle type conversions manually.
     - Only `MessageTextInput` can have `tool_mode=True`; other input types cannot have `tool_mode`.
   - **Outputs**:
     - Define outputs using the `Output` class, specifying:
       - `name`: The unique identifier for the output.
       - `display_name`: A human-readable name for the output.
       - `method`: The method that generates the output data.
       - `info`: A description of what the output represents.
     - Ensure output methods return data in the expected formats (e.g., `Message`, `Data`, `list[Data]`).
     - All methods should explicitly define their return types using type hints (e.g., `def method(self) -> Data:`).
     - Import `Data` using `from langflow.schema import Data`.
     - Outputs must be appropriately connected to the methods that produce them.

2. **Input Types**:
   Use the appropriate input types from `langflow.io`:
   - `MessageTextInput`
   - `MultilineInput`
   - `IntInput`
   - `FloatInput`
   - `BoolInput`
   - `DropdownInput`
   - `FileInput`
   - `HandleInput`
   - `DataInput`
   - `NestedDictInput`
   - `DictInput`
   - `SecretStrInput`

   **Guidelines**:
   - Set `is_list=True` when expecting lists.
   - Use `advanced=True` for optional or less frequently used inputs.
   - Provide clear `display_name` and `info` descriptions for each input.
   - For numerical inputs that require `tool_mode`, use `MessageTextInput` and convert the string to a number in your code.
   - Only `MessageTextInput` can have `tool_mode=True`.
   - `BoolInput` and `DropdownInput` should be used without `tool_mode`.

3. **Error Handling and Logging**:
   - **Error Handling**:
     - Use `try-except` blocks to handle potential errors gracefully.
     - Include both API-specific and general errors.
     - Provide detailed and informative error messages.
     - Return `Data` objects even when errors occur.
     - Use `self.status()` to provide feedback about the operation.
     - Include relevant metadata in status updates.
   - **Logging**:
     - Use `self.log()` as the primary logging method in components.
     - Log important steps for easier debugging.
     - Place logging statements at key points:
       - Before API calls to log payloads.
       - After receiving responses.
       - During error handling.
       - When processing inputs/outputs.
     - Log relevant data that helps debug issues:
       - Input parameters.
       - Constructed payloads.
       - Response data.
       - Error details.
     - Avoid using `print()` or external logging libraries, as they won't work in Langflow.

4. **Data Handling and Return Types**:
   - Return `Data` objects directly from methods.
   - Ensure all methods explicitly define their return types using type hints.
   - Import `Data` using `from langflow.schema import Data`.
   - Return types in methods should be Langflow's `Data` objects instead of Python dictionaries.
   - Handle type conversions manually (e.g., convert strings to integers in your code).
   - Validate inputs and provide informative error messages if inputs are incorrect.

5. **Code Quality and Best Practices**:
   - Use descriptive variable names and include comments where necessary.
   - Handle data types carefully, ensuring inputs and outputs match expected formats.
   - Implement proper error handling with informative error messages.
   - Provide clear `info` messages for inputs to help users understand what is expected.
   - Write descriptive `description` fields to explain your component's functionality.
   - Organize code logically and group related inputs together.
   - Ensure the code follows Langflow's best practices and conventions.
   - **Component vs. Tool**:
     - Use `langflow.custom.Component` for general components.
     - Inherit from `Component` instead of `LCToolComponent`.
     - `StructuredTool` or Pydantic schemas are no longer needed. That is due to the tool mode that didn't exist previously.

6. **Additional Development Guidelines**:

   **Testing and Debugging**:
   - Use logging to track component behavior.
   - Test edge cases and error conditions.
   - Verify API integration works correctly.
   - Check input validation.
   - Ensure proper error handling.
   - Validate output formats.
   - Document any limitations or requirements.

   **API Integration Guidelines**:
   - Start with a thorough API documentation review.
   - Document the exact payload structure required.
   - Test API calls independently before implementing.
   - Include comprehensive error handling.
   - Log both request and response data.
   - Validate API responses before processing.
   - Handle different response formats appropriately.

   **Development Workflow**:
   - Begin with API/service documentation review.
   - Plan logging strategy before implementation.
   - Implement basic functionality first.
   - Add comprehensive logging statements.
   - Test with various input scenarios.
   - Validate error handling.
   - Review and optimize code.
   - Document component behavior.