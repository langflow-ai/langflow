import re


def extract_input_variables(data):
    """
    Extracts input variables from the template and adds them to the input_variables field.
    """
    for node in data["nodes"]:
        try:
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
        except:
            pass
    return data


def get_root_node(data):
    """
    Returns the root node of the template.
    """
    root = None
    incoming_edges = {edge["source"] for edge in data["edges"]}
    for node in data["nodes"]:
        if node["id"] not in incoming_edges:
            root = node
            break
    return root


def build_json(root, nodes, edges):
    edge_ids = [edge["source"] for edge in edges if edge["target"] == root["id"]]
    local_nodes = [node for node in nodes if node["id"] in edge_ids]

    if "node" not in root["data"]:
        return build_json(local_nodes[0], nodes, edges)

    final_dict = root["data"]["node"]["template"].copy()

    for key, value in final_dict.items():
        if key == "_type":
            continue

        module_type = value["type"]
        if module_type == "Tool":
            pass
        if module_type in ["str", "bool", "int", "float"]:
            value = value["value"]
        elif "dict" in module_type:
            value = {}
        else:
            # if value['list']:
            children = [
                c
                for c in local_nodes
                if module_type
                in [c["data"]["type"]] + c["data"]["node"]["base_classes"]
            ]
            # else:
            #     children = next((c for c in local_nodes if type in [c['data']['type']] + c['data']['node']['base_classes']), None)
            if value["required"] and not children:
                raise ValueError(f"No child with type {module_type} found")
            values = [
                build_json(child, nodes, edges) for child in children
            ]  # if children else None
            value = list(values) if value["list"] else next(iter(values), None)
        final_dict[key] = value
    return final_dict
