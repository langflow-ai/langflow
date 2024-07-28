from langflow.code_gen.component import generate_script


def generate_script_from_graph(graph):
    script = generate_script(*graph.sort_components())
    return script
