import contextlib
import re
from typing import Dict


def extract_input_variables(nodes):
    """
    Extracts input variables from the template
    and adds them to the input_variables field.
    """
    for node in nodes:
        with contextlib.suppress(Exception):
            if "input_variables" in node["data"]["node"]["template"]:
                if node["data"]["node"]["template"]["_type"] == "prompt":
                    variables = re.findall(
                        r"\{(.*?)\}",
                        node["data"]["node"]["template"]["template"]["value"],
                    )
                elif node["data"]["node"]["template"]["_type"] == "few_shot":
                    variables = re.findall(
                        r"\{(.*?)\}",
                        node["data"]["node"]["template"]["prefix"]["value"]
                        + node["data"]["node"]["template"]["suffix"]["value"],
                    )
                else:
                    variables = []
                node["data"]["node"]["template"]["input_variables"]["value"] = variables
    return nodes


def get_root_vertex(graph):
    """
    Returns the root node of the template.
    """
    incoming_edges = {edge.source_id for edge in graph.edges}

    if not incoming_edges and len(graph.vertices) == 1:
        return graph.vertices[0]

    return next((node for node in graph.vertices if node.id not in incoming_edges), None)


def build_json(root, graph) -> Dict:
    if "node" not in root.data:
        # If the root node has no "node" key, then it has only one child,
        # which is the target of the single outgoing edge
        edge = root.edges[0]
        local_nodes = [edge.target]
    else:
        # Otherwise, find all children whose type matches the type
        # specified in the template
        node_type = root.node_type
        local_nodes = graph.get_nodes_with_target(root)

    if len(local_nodes) == 1:
        return build_json(local_nodes[0], graph)
    # Build a dictionary from the template
    template = root.data["node"]["template"]
    final_dict = template.copy()

    for key, value in final_dict.items():
        if key == "_type":
            continue

        node_type = value["type"]

        if "value" in value and value["value"] is not None:
            # If the value is specified, use it
            value = value["value"]
        elif "dict" in node_type:
            # If the value is a dictionary, create an empty dictionary
            value = {}
        else:
            # Otherwise, recursively build the child nodes
            children = []
            for local_node in local_nodes:
                node_children = graph.get_children_by_node_type(local_node, node_type)
                children.extend(node_children)

            if value["required"] and not children:
                raise ValueError(f"No child with type {node_type} found")
            values = [build_json(child, graph) for child in children]
            value = (
                list(values) if value["list"] else next(iter(values), None)  # type: ignore
            )
        final_dict[key] = value

    return final_dict
