def get_model_name(llm, display_name: str | None = "Custom"):
    attributes_to_check = ["model_name", "model", "model_id", "deployment_name"]

    # Use a generator expression with next() to find the first matching attribute
    model_name = next((getattr(llm, attr) for attr in attributes_to_check if hasattr(llm, attr)), None)

    # If no matching attribute is found, return the class name as a fallback
    return model_name if model_name is not None else display_name
