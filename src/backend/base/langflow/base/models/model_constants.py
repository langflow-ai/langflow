class ModelConstants:
    """Class to hold model-related constants. To solve circular import issue."""

    PROVIDER_NAMES: list[str] = []
    MODEL_INFO: dict[str, dict[str, str | list]] = {}  # Adjusted type hint

    @staticmethod
    def initialize():
        from langflow.base.models.model_utils import get_model_info  # Delayed import

        model_info = get_model_info()
        ModelConstants.MODEL_INFO = model_info
        ModelConstants.PROVIDER_NAMES = [
            str(model.get("display_name"))
            for model in model_info.values()
            if isinstance(model.get("display_name"), str)
        ]
