import contextlib
import re


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


def get_root_node(nodes, edges):
    """
    Returns the root node of the template.
    """
    incoming_edges = {edge["source"] for edge in edges}
    return next((node for node in nodes if node["id"] not in incoming_edges), None)


def build_json(root, nodes, edges):
    """
    Builds a json from the nodes and edges
    """
    edge_ids = [edge["source"] for edge in edges if edge["target"] == root["id"]]
    local_nodes = [node for node in nodes if node["id"] in edge_ids]

    if "node" not in root["data"]:
        return build_json(local_nodes[0], nodes, edges)

    final_dict = root["data"]["node"]["template"].copy()

    for key, value in final_dict.items():
        if key == "_type":
            continue

        module_type = value["type"]

        if "value" in value and value["value"] is not None:
            value = value["value"]
        elif "dict" in module_type:
            value = {}
        else:
            children = []
            for c in local_nodes:
                module_types = [c["data"]["type"]]
                if "node" in c["data"]:
                    module_types += c["data"]["node"]["base_classes"]
                if module_type in module_types:
                    children.append(c)

            if value["required"] and not children:
                raise ValueError(f"No child with type {module_type} found")
            values = [build_json(child, nodes, edges) for child in children]
            value = list(values) if value["list"] else next(iter(values), None)
        final_dict[key] = value
    return final_dict
