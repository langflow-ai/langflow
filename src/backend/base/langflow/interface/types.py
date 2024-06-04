from langflow.custom.utils import build_custom_components


def get_all_types_dict(components_paths):
    """Get all types dictionary combining native and custom components."""
    custom_components_from_file = build_custom_components(components_paths=components_paths)
    return custom_components_from_file


def get_all_components(components_paths, as_dict=False):
    """Get all components names combining native and custom components."""
    all_types_dict = get_all_types_dict(components_paths)
    components = [] if not as_dict else {}
    for category in all_types_dict.values():
        for component in category.values():
            component["name"] = component["display_name"]
            if as_dict:
                components[component["name"]] = component
            else:
                components.append(component)
    return components
