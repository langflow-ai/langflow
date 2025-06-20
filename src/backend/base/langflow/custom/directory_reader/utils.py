import asyncio

from loguru import logger

from langflow.custom.directory_reader.directory_reader import DirectoryReader
from langflow.template.frontend_node.custom_components import CustomComponentFrontendNode


def merge_nested_dicts_with_renaming(dict1, dict2):
    for key, value in dict2.items():
        if key in dict1 and isinstance(value, dict) and isinstance(dict1.get(key), dict):
            for sub_key, sub_value in value.items():
                # if sub_key in dict1[key]:
                #     new_key = get_new_key(dict1[key], sub_key)
                #     dict1[key][new_key] = sub_value
                # else:
                dict1[key][sub_key] = sub_value
        else:
            dict1[key] = value
    return dict1


def build_invalid_menu(invalid_components):
    """Build the invalid menu."""
    if not invalid_components.get("menu"):
        return {}

    logger.debug("------------------- INVALID COMPONENTS -------------------")
    invalid_menu = {}
    for menu_item in invalid_components["menu"]:
        menu_name = menu_item["name"]
        invalid_menu[menu_name] = build_invalid_menu_items(menu_item)
    return invalid_menu


def build_valid_menu(valid_components):
    """Build the valid menu."""
    valid_menu = {}
    logger.debug("------------------- VALID COMPONENTS -------------------")
    for menu_item in valid_components["menu"]:
        menu_name = menu_item["name"]
        valid_menu[menu_name] = build_menu_items(menu_item)
    return valid_menu


def build_and_validate_all_files(reader: DirectoryReader, file_list):
    """Build and validate all files."""
    data = reader.build_component_menu_list(file_list)

    valid_components = reader.filter_loaded_components(data=data, with_errors=False)
    invalid_components = reader.filter_loaded_components(data=data, with_errors=True)

    return valid_components, invalid_components


async def abuild_and_validate_all_files(reader: DirectoryReader, file_list):
    """Build and validate all files."""
    data = await reader.abuild_component_menu_list(file_list)

    valid_components = reader.filter_loaded_components(data=data, with_errors=False)
    invalid_components = reader.filter_loaded_components(data=data, with_errors=True)

    return valid_components, invalid_components


def load_files_from_path(path: str):
    """Load all files from a given path."""
    reader = DirectoryReader(path, compress_code_field=False)

    return reader.get_files()


def build_custom_component_list_from_path(path: str):
    """Build a list of custom components for the langchain from a given path."""
    file_list = load_files_from_path(path)
    reader = DirectoryReader(path, compress_code_field=False)

    valid_components, invalid_components = build_and_validate_all_files(reader, file_list)

    valid_menu = build_valid_menu(valid_components)
    invalid_menu = build_invalid_menu(invalid_components)

    return merge_nested_dicts_with_renaming(valid_menu, invalid_menu)


async def abuild_custom_component_list_from_path(path: str):
    """Build a list of custom components for the langchain from a given path."""
    file_list = await asyncio.to_thread(load_files_from_path, path)
    reader = DirectoryReader(path, compress_code_field=False)

    valid_components, invalid_components = await abuild_and_validate_all_files(reader, file_list)

    valid_menu = build_valid_menu(valid_components)
    invalid_menu = build_invalid_menu(invalid_components)

    return merge_nested_dicts_with_renaming(valid_menu, invalid_menu)


def create_invalid_component_template(component, component_name):
    """Create a template for an invalid component."""
    component_code = component["code"]
    component_frontend_node = CustomComponentFrontendNode(
        description="ERROR - Check your Python Code",
        display_name=f"ERROR - {component_name}",
    )

    component_frontend_node.error = component.get("error", None)
    field = component_frontend_node.template.get_field("code")
    field.value = component_code
    component_frontend_node.template.update_field("code", field)
    return component_frontend_node.model_dump(by_alias=True, exclude_none=True)


def log_invalid_component_details(component) -> None:
    """Log details of an invalid component."""
    logger.debug(component)
    logger.debug(f"Component Path: {component.get('path', None)}")
    logger.debug(f"Component Error: {component.get('error', None)}")


def build_invalid_component(component):
    """Build a single invalid component."""
    component_name = component["name"]
    component_template = create_invalid_component_template(component, component_name)
    log_invalid_component_details(component)
    return component_name, component_template


def build_invalid_menu_items(menu_item):
    """Build invalid menu items for a given menu."""
    menu_items = {}
    for component in menu_item["components"]:
        try:
            component_name, component_template = build_invalid_component(component)
            menu_items[component_name] = component_template
            logger.debug(f"Added {component_name} to invalid menu.")
        except Exception:  # noqa: BLE001
            logger.exception(f"Error while creating custom component [{component_name}]")
    return menu_items


def get_new_key(dictionary, original_key):
    counter = 1
    new_key = original_key + " (" + str(counter) + ")"
    while new_key in dictionary:
        counter += 1
        new_key = original_key + " (" + str(counter) + ")"
    return new_key


def determine_component_name(component):
    """Determine the name of the component."""
    # component_output_types = component["output_types"]
    # if len(component_output_types) == 1:
    #     return component_output_types[0]
    # else:
    #     file_name = component.get("file").split(".")[0]
    #     return "".join(word.capitalize() for word in file_name.split("_")) if "_" in file_name else file_name
    return component["name"]


def build_menu_items(menu_item):
    """Build menu items for a given menu."""
    menu_items = {}
    logger.debug(f"Building {len(menu_item['components'])} {menu_item['name']} components")
    for component_name, component_template, component in menu_item["components"]:
        try:
            menu_items[component_name] = component_template
        except Exception:  # noqa: BLE001
            logger.exception(f"Error while building custom component {component['output_types']}")
    return menu_items
