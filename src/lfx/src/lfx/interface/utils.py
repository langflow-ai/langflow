from string import Formatter


def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract variable names from a prompt string using Python's built-in string formatter.
    Uses the same convention as Python's .format() method:
    - Single braces {name} are variable placeholders
    - Double braces {{name}} are escape sequences that render as literal {name}.
    """
    formatter = Formatter()
    variables: list[str] = []
    seen: set[str] = set()
    # Use local bindings for micro-optimization
    variables_append = variables.append
    seen_add = seen.add
    seen_contains = seen.__contains__
    for _, field_name, _, _ in formatter.parse(prompt):
        if field_name and not seen_contains(field_name):
            variables_append(field_name)
            seen_add(field_name)
    return variables
