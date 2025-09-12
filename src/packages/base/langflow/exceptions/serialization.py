from typing import Any

from fastapi import HTTPException, status


class SerializationError(HTTPException):
    """Exception raised when there are errors serializing data to JSON."""

    def __init__(
        self,
        detail: str,
        original_error: Exception | None = None,
        data: Any = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.original_error = original_error
        self.data = data

    @classmethod
    def from_exception(cls, exc: Exception, data: Any = None) -> "SerializationError":
        """Create a SerializationError from an existing exception."""
        errors = exc.args[0] if exc.args else []

        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, TypeError):
                    if "'coroutine'" in str(error):
                        return cls(
                            detail=(
                                "The component contains async functions that need to be awaited. Please add 'await' "
                                "before any async function calls in your component code."
                            ),
                            original_error=exc,
                            data=data,
                        )
                    if "vars()" in str(error):
                        return cls(
                            detail=(
                                "The component contains objects that cannot be converted to JSON. Please ensure all "
                                "properties and return values in your component are basic Python types like strings, "
                                "numbers, lists, or dictionaries."
                            ),
                            original_error=exc,
                            data=data,
                        )

        # Generic error for other cases
        return cls(
            detail=(
                "The component returned invalid data. Please check that all values in your component (properties, "
                "return values, etc.) are basic Python types that can be converted to JSON."
            ),
            original_error=exc,
            data=data,
        )
