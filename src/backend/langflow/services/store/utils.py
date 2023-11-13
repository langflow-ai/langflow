from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from langflow.services.store.schema import ListComponentResponse
    from langflow.services.store.service import StoreService


def process_tags_for_post(component_dict):
    tags = component_dict.pop("tags", None)
    if tags and all(isinstance(tag, str) for tag in tags):
        component_dict["tags"] = [{"tags_id": tag} for tag in tags]
    return component_dict


def update_components_with_user_data(
    components: List["ListComponentResponse"],
    store_service: "StoreService",
    store_api_Key: str,
):
    """
    Updates the components with the user data (liked_by_user and in_users_collection)
    """
    liked_by_user_ids = store_service.get_liked_by_user_components(
        component_ids=[str(component.id) for component in components],
        api_key=store_api_Key,
    )
    in_users_collection_ids = store_service.get_components_in_users_collection(
        component_ids=[str(component.id) for component in components],
        api_key=store_api_Key,
    )
    # Now we need to set the liked_by_user attribute
    for component in components:
        component.liked_by_user = str(component.id) in liked_by_user_ids
        component.in_user_collection = str(component.id) in in_users_collection_ids
    return components
