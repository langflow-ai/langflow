"""Cross-module BaseModel for handling re-exported classes.

This module provides a metaclass and base model that enable isinstance checks
to work across module boundaries for Pydantic models. This is particularly useful
when the same class is re-exported from different modules (e.g., lfx.Message vs
langflow.schema.Message) but Python's isinstance() checks fail due to different
module paths.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CrossModuleMeta(type(BaseModel)):  # type: ignore[misc]
    """Metaclass that enables cross-module isinstance checks for Pydantic models.

    This metaclass overrides __instancecheck__ to perform structural type checking
    based on the model's fields rather than strict class identity. This allows
    instances of the same model from different module paths to be recognized as
    compatible.
    """

    def __instancecheck__(cls, instance: Any) -> bool:
        """Check if instance is compatible with this class across module boundaries.

        First performs a standard isinstance check. If that fails, falls back to
        checking if the instance has all required Pydantic model attributes and
        a compatible set of model fields.

        Args:
            instance: The object to check.

        Returns:
            bool: True if instance is compatible with this class.
        """
        # First try standard isinstance check
        if type.__instancecheck__(cls, instance):
            return True

        # If that fails, check for cross-module compatibility
        # An object is cross-module compatible if it:
        # 1. Has model_fields attribute (is a Pydantic model)
        # 2. Has the same __class__.__name__
        # 3. Has compatible model fields
        if not hasattr(instance, "model_fields"):
            return False

        # Check if class names match
        if instance.__class__.__name__ != cls.__name__:
            return False

        # Check if the instance has all required fields from cls
        cls_fields = set(cls.model_fields.keys()) if hasattr(cls, "model_fields") else set()
        instance_fields = set(instance.model_fields.keys())

        # The instance must have at least the same fields as the class
        # (it can have more, but not fewer required fields)
        return cls_fields.issubset(instance_fields)


class CrossModuleModel(BaseModel, metaclass=CrossModuleMeta):
    """Base Pydantic model with cross-module isinstance support.

    This class should be used as the base for models that may be re-exported
    from different modules. It enables isinstance() checks to work across
    module boundaries by using structural type checking.

    Example:
        >>> class Message(CrossModuleModel):
        ...     text: str
        ...
        >>> # Even if Message is imported from different paths:
        >>> from lfx.schema.message import Message as LfxMessage
        >>> from langflow.schema import Message as LangflowMessage
        >>> msg = LfxMessage(text="hello")
        >>> isinstance(msg, LangflowMessage)  # True (with cross-module support)
    """
