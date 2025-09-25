"""Data Transformer Component for processing and validating data."""

import json
import re
from typing import Any, Dict, List

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data


class DataTransformerComponent(Component):
    """Component for transforming and validating data."""

    display_name = "Data Transformer"
    category: str = "processing"
    description = "Transform, validate, and format data with various operations"
    documentation = "https://docs.yourcompany.com/data-transformer"
    icon = "shuffle"
    name = "DataTransformerComponent"

    inputs = [
        MessageTextInput(
            name="input_data",
            display_name="Input Data",
            info="JSON string or text to transform",
            value="{}",
        ),
        DropdownInput(
            name="operation",
            display_name="Transform Operation",
            options=[
                "format_json",
                "extract_fields",
                "validate_email",
                "clean_text",
                "to_uppercase",
                "to_lowercase",
                "extract_numbers",
                "extract_urls",
                "mask_sensitive_data",
            ],
            value="format_json",
            info="Select the transformation operation to perform",
        ),
        MessageTextInput(
            name="operation_params",
            display_name="Operation Parameters",
            info="JSON string of parameters for the operation",
            value="{}",
        ),
        BoolInput(
            name="strict_validation",
            display_name="Strict Validation",
            value=False,
            info="Enable strict validation mode",
        ),
    ]

    outputs = [
        Output(
            display_name="Transformed Data",
            name="transformed_data",
            method="build_transformed_data",
        ),
        Output(
            display_name="Validation Result",
            name="validation_result",
            method="build_validation_result",
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transformation_result = None
        self.validation_errors = []

    async def build_transformed_data(self) -> Data:
        """Transform the input data based on the selected operation."""
        try:
            # Parse operation parameters
            try:
                params = (
                    json.loads(self.operation_params)
                    if self.operation_params.strip()
                    else {}
                )
            except json.JSONDecodeError:
                self.status = "❌ Invalid JSON in operation parameters"
                return Data(
                    data={
                        "error": "Invalid JSON in operation parameters",
                        "params": self.operation_params,
                    }
                )

            # Perform the transformation
            result = await self._perform_transformation(
                self.input_data, self.operation, params
            )

            self.transformation_result = result
            self.status = f"✅ {self.operation} completed successfully"

            return Data(
                data={
                    "original": self.input_data,
                    "transformed": result,
                    "operation": self.operation,
                    "parameters": params,
                }
            )

        except Exception as e:
            self.status = f"❌ Transformation error: {str(e)}"
            return Data(
                data={
                    "error": str(e),
                    "operation": self.operation,
                    "input": self.input_data,
                }
            )

    async def build_validation_result(self) -> Data:
        """Return validation results for the transformation."""
        return Data(
            data={
                "is_valid": len(self.validation_errors) == 0,
                "errors": self.validation_errors,
                "strict_mode": self.strict_validation,
                "operation": self.operation,
            }
        )

    async def _perform_transformation(
        self, data: str, operation: str, params: Dict[str, Any]
    ) -> Any:
        """Perform the actual transformation operation."""
        self.validation_errors = []

        if operation == "format_json":
            return await self._format_json(data, params)
        elif operation == "extract_fields":
            return await self._extract_fields(data, params)
        elif operation == "validate_email":
            return await self._validate_email(data, params)
        elif operation == "clean_text":
            return await self._clean_text(data, params)
        elif operation == "to_uppercase":
            return data.upper()
        elif operation == "to_lowercase":
            return data.lower()
        elif operation == "extract_numbers":
            return await self._extract_numbers(data, params)
        elif operation == "extract_urls":
            return await self._extract_urls(data, params)
        elif operation == "mask_sensitive_data":
            return await self._mask_sensitive_data(data, params)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def _format_json(self, data: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Format and validate JSON data."""
        try:
            parsed = json.loads(data)

            # Apply formatting options
            indent = params.get("indent", 2)
            sort_keys = params.get("sort_keys", False)

            formatted = json.dumps(parsed, indent=indent, sort_keys=sort_keys)

            return {"formatted": formatted, "parsed": parsed, "is_valid_json": True}
        except json.JSONDecodeError as e:
            if self.strict_validation:
                self.validation_errors.append(f"Invalid JSON: {str(e)}")
            return {
                "formatted": data,
                "parsed": None,
                "is_valid_json": False,
                "error": str(e),
            }

    async def _extract_fields(
        self, data: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract specific fields from JSON data."""
        try:
            parsed = json.loads(data)
            fields = params.get("fields", [])

            if not fields:
                self.validation_errors.append("No fields specified for extraction")
                return {
                    "extracted": {},
                    "all_fields": (
                        list(parsed.keys()) if isinstance(parsed, dict) else []
                    ),
                }

            extracted = {}
            for field in fields:
                if isinstance(parsed, dict) and field in parsed:
                    extracted[field] = parsed[field]
                elif self.strict_validation:
                    self.validation_errors.append(f"Field '{field}' not found")

            return {
                "extracted": extracted,
                "requested_fields": fields,
                "available_fields": (
                    list(parsed.keys()) if isinstance(parsed, dict) else []
                ),
            }

        except json.JSONDecodeError:
            if self.strict_validation:
                self.validation_errors.append("Input is not valid JSON")
            return {"extracted": {}, "error": "Invalid JSON input"}

    async def _validate_email(
        self, data: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate email addresses in the data."""
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, data)

        valid_emails = []
        invalid_emails = []

        for email in emails:
            # Basic validation
            if "@" in email and "." in email.split("@")[1]:
                valid_emails.append(email)
            else:
                invalid_emails.append(email)
                if self.strict_validation:
                    self.validation_errors.append(f"Invalid email format: {email}")

        return {
            "valid_emails": valid_emails,
            "invalid_emails": invalid_emails,
            "total_found": len(emails),
            "original_text": data,
        }

    async def _clean_text(self, data: str, params: Dict[str, Any]) -> str:
        """Clean and normalize text data."""
        text = data

        # Remove extra whitespace
        if params.get("remove_extra_whitespace", True):
            text = re.sub(r"\s+", " ", text).strip()

        # Remove special characters
        if params.get("remove_special_chars", False):
            text = re.sub(r"[^a-zA-Z0-9\s]", "", text)

        # Remove HTML tags
        if params.get("remove_html_tags", False):
            text = re.sub(r"<[^>]+>", "", text)

        return text

    async def _extract_numbers(
        self, data: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract numbers from text data."""
        # Extract integers
        integers = [int(x) for x in re.findall(r"-?\d+", data)]

        # Extract floats
        floats = [float(x) for x in re.findall(r"-?\d+\.\d+", data)]

        return {
            "integers": integers,
            "floats": floats,
            "all_numbers": integers + floats,
            "count": len(integers) + len(floats),
        }

    async def _extract_urls(self, data: str, params: Dict[str, Any]) -> List[str]:
        """Extract URLs from text data."""
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        urls = re.findall(url_pattern, data)
        return urls

    async def _mask_sensitive_data(self, data: str, params: Dict[str, Any]) -> str:
        """Mask sensitive data in text."""
        text = data
        mask_char = params.get("mask_char", "*")

        # Mask email addresses
        if params.get("mask_emails", True):
            email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            text = re.sub(
                email_pattern,
                lambda m: f"{m.group()[:2]}{mask_char * 5}@{mask_char * 3}.com",
                text,
            )

        # Mask phone numbers (simple pattern)
        if params.get("mask_phones", True):
            phone_pattern = r"\b\d{3}-\d{3}-\d{4}\b"
            text = re.sub(
                phone_pattern, f"{mask_char * 3}-{mask_char * 3}-{mask_char * 4}", text
            )

        # Mask credit card numbers (simple pattern)
        if params.get("mask_credit_cards", True):
            cc_pattern = r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"
            text = re.sub(
                cc_pattern,
                f"{mask_char * 4} {mask_char * 4} {mask_char * 4} {mask_char * 4}",
                text,
            )

        return text


# Component is automatically registered when imported
