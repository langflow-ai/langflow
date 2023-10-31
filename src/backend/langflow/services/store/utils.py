def process_tags_for_post(component_dict):
    tags = component_dict.pop("tags", None)
    if tags and all(isinstance(tag, str) for tag in tags):
        component_dict["tags"] = [{"tags_id": tag} for tag in tags]
    return component_dict
