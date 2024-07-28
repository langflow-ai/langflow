import re


def get_variable_name(instance):
    return re.sub(r"[^0-9a-zA-Z_]", "_", instance._id.lower())


def generate_import_statement(instance):
    class_name = instance.__class__.__name__
    module_path = instance.__class__.__module__
    parts = module_path.split(".")

    # Construct the correct import statement
    if len(parts) > 2:
        module_path = ".".join(parts)
        return f"from {module_path} import {class_name}"
    else:
        return f"from {module_path} import {class_name}"
