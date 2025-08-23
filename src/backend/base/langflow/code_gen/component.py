from langflow.code_gen.generic import generate_import_statement, get_variable_name


def generate_call_string(instance):
    variable_name = get_variable_name(instance)
    if hasattr(instance, "_call_inputs"):
        args = ", ".join(
            f"{key}={get_variable_name(value.__self__)}.{value.__name__}" if callable(value) else f"{key}={value!r}"
            for key, value in instance._call_inputs.items()
        )
        if args:
            return f"{variable_name}.set({args})"


def generate_instantiation_string(instance):
    if isinstance(instance, tuple):
        raise ValueError(
            "An instance of Component was expected, but a tuple was provided. You might be trying to call the component instead of calling the `set` method."
        )
    class_name = instance.__class__.__name__
    instance_id = instance._id
    variable_name = get_variable_name(instance)
    return f"{variable_name} = {class_name}(_id='{instance_id}')"


def generate_graph_instantiation_string(start, end):
    return f"graph = Graph(start={get_variable_name(start)}, end={get_variable_name(end)})"


def generate_script(*, instances, start=None, end=None):
    import_statements = set()
    instantiation_strings = []
    call_strings = []

    for instance in instances:
        import_statements.add(generate_import_statement(instance))
        instantiation_strings.append(generate_instantiation_string(instance))
        call_string = generate_call_string(instance)

        if call_string:
            call_strings.append(call_string)

    if start is None or end is None:
        graph_instantiation_code = ""
    else:
        graph_instantiation_code = generate_graph_instantiation_string(start, end)
        # Add Graph import statement to the beginning of the script
        import_statements.add("from langflow.graph.graph.base import Graph")
    import_code = "\n".join(sorted(import_statements))
    instantiation_code = "\n".join(instantiation_strings)
    call_code = "\n".join(call_strings)
    return f"{import_code}\n\n{instantiation_code}\n\n{call_code}\n\n{graph_instantiation_code}".strip()
