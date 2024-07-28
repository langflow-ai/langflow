from langflow.code_gen.generic import generate_import_statement, get_variable_name


def generate_call_string(instance):
    variable_name = get_variable_name(instance)
    if hasattr(instance, "_call_inputs"):
        args = ", ".join(
            f"{key}={get_variable_name(value.__self__)}.{value.__name__}" if callable(value) else f"{key}={repr(value)}"
            for key, value in instance._call_inputs.items()
        )
        if args:
            return f"{variable_name}({args})"


def generate_instantiation_string(instance):
    class_name = instance.__class__.__name__
    instance_id = instance._id
    variable_name = get_variable_name(instance)
    return f"{variable_name} = {class_name}(_id='{instance_id}')"


def generate_script(*instances):
    import_statements = set()
    instantiation_strings = []
    call_strings = []

    for instance in instances:
        import_statements.add(generate_import_statement(instance))
        instantiation_strings.append(generate_instantiation_string(instance))
        call_string = generate_call_string(instance)

        if call_string:
            call_strings.append(call_string)

    import_code = "\n".join(sorted(import_statements))
    instantiation_code = "\n".join(instantiation_strings)
    call_code = "\n".join(call_strings)

    return f"{import_code}\n\n{instantiation_code}\n\n{call_code}"
