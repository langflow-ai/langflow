import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from httpx import HTTPError, HTTPStatusError
from loguru import logger

from langflow.services.base import Service
from langflow.services.store.exceptions import APIKeyError, FilterError, ForbiddenError
from langflow.services.store.schema import (
    CreateComponentResponse,
    DownloadComponentResponse,
    ListComponentResponse,
    ListComponentResponseModel,
    StoreComponentCreate,
)
from langflow.services.store.utils import (
    process_component_data,
    process_tags_for_post,
    update_components_with_user_data,
)

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService

from contextlib import asynccontextmanager
from contextvars import ContextVar

user_data_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar("user_data", default=None)


@asynccontextmanager
async def user_data_context(store_service: "StoreService", api_key: Optional[str] = None):
    # Fetch and set user data to the context variable
    if api_key:
        try:
            user_data, _ = await store_service._get(
                f"{store_service.base_url}/users/me", api_key, params={"fields": "id"}
            )
            user_data_var.set(user_data[0])
        except HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise ValueError("Invalid API key")
    try:
        yield
    finally:
        # Clear the user data from the context variable
        user_data_var.set(None)


def get_id_from_search_string(search_string: str) -> Optional[str]:
    """
    Extracts the ID from a search string.

    Args:
        search_string (str): The search string to extract the ID from.

    Returns:
        Optional[str]: The extracted ID, or None if no ID is found.
    """
    possible_id: Optional[str] = search_string
    if "www.langflow.store/store/" in search_string:
        possible_id = search_string.split("/")[-1]

    try:
        possible_id = str(UUID(search_string))
    except ValueError:
        possible_id = None
    return possible_id


class StoreService(Service):
    """This is a service that integrates langflow with the store which
    is a Directus instance. It allows to search, get and post components to
    the store."""

    name = "store_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_url = self.settings_service.settings.store_url
        self.download_webhook_url = self.settings_service.settings.download_webhook_url
        self.like_webhook_url = self.settings_service.settings.like_webhook_url
        self.components_url = f"{self.base_url}/items/components"
        self.default_fields = [
            "id",
            "name",
            "description",
            "user_created.username",
            "is_component",
            "tags.tags_id.name",
            "tags.tags_id.id",
            "count(liked_by)",
            "count(downloads)",
            "metadata",
            "last_tested_version",
            "private",
        ]
        self.timeout = 30

    # Create a context manager that will use the api key to
    # get the user data and all requests inside the context manager
    # will make a property return that data
    # Without making the request multiple times

    async def check_api_key(self, api_key: str):
        # Check if the api key is valid
        # If it is, return True
        # If it is not, return False
        try:
            user_data, _ = await self._get(f"{self.base_url}/users/me", api_key, params={"fields": "id"})

            return "id" in user_data[0]
        except HTTPStatusError as exc:
            if exc.response.status_code in [403, 401]:
                return False
            else:
                raise ValueError(f"Unexpected status code: {exc.response.status_code}")
        except Exception as exc:
            raise ValueError(f"Unexpected error: {exc}")

    async def _get(
        self, url: str, api_key: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Utility method to perform GET requests."""
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            headers = {}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params, timeout=self.timeout)
                response.raise_for_status()
            except HTTPError as exc:
                raise exc
            except Exception as exc:
                raise ValueError(f"GET failed: {exc}")
        json_response = response.json()
        result = json_response["data"]
        metadata = {}
        if "meta" in json_response:
            metadata = json_response["meta"]

        if isinstance(result, dict):
            return [result], metadata
        return result, metadata

    async def call_webhook(self, api_key: str, webhook_url: str, component_id: UUID) -> None:
        # The webhook is a POST request with the data in the body
        # For now we are calling it just for testing
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url, headers=headers, json={"component_id": str(component_id)}, timeout=self.timeout
                )
                response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise exc
        except Exception as exc:
            logger.debug(f"Webhook failed: {exc}")

    def build_tags_filter(self, tags: List[str]):
        tags_filter: Dict[str, Any] = {"tags": {"_and": []}}
        for tag in tags:
            tags_filter["tags"]["_and"].append({"_some": {"tags_id": {"name": {"_eq": tag}}}})
        return tags_filter

    async def count_components(
        self,
        filter_conditions: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        use_api_key: Optional[bool] = False,
    ) -> int:
        params = {"aggregate": json.dumps({"count": "*"})}
        if filter_conditions:
            params["filter"] = json.dumps({"_and": filter_conditions})

        api_key = api_key if use_api_key else None

        results, _ = await self._get(self.components_url, api_key, params)
        return int(results[0].get("count", 0))

    @staticmethod
    def build_search_filter_conditions(query: str):
        # instead of build the param ?search=query, we will build the filter
        # that will use _icontains (case insensitive)
        conditions: Dict[str, Any] = {"_or": []}
        conditions["_or"].append({"name": {"_icontains": query}})
        conditions["_or"].append({"description": {"_icontains": query}})
        conditions["_or"].append({"tags": {"tags_id": {"name": {"_icontains": query}}}})
        conditions["_or"].append({"user_created": {"username": {"_icontains": query}}})
        return conditions

    def build_filter_conditions(
        self,
        component_id: Optional[str] = None,
        search: Optional[str] = None,
        private: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        is_component: Optional[bool] = None,
        filter_by_user: Optional[bool] = False,
        liked: Optional[bool] = False,
        store_api_key: Optional[str] = None,
    ):
        filter_conditions = []

        if component_id is None:
            component_id = get_id_from_search_string(search) if search else None

        if search is not None and component_id is None:
            search_conditions = self.build_search_filter_conditions(search)
            filter_conditions.append(search_conditions)

        if private is not None:
            filter_conditions.append({"private": {"_eq": private}})

        if tags:
            tags_filter = self.build_tags_filter(tags)
            filter_conditions.append(tags_filter)
        if component_id is not None:
            filter_conditions.append({"id": {"_eq": component_id}})
        if is_component is not None:
            filter_conditions.append({"is_component": {"_eq": is_component}})
        if liked and store_api_key:
            liked_filter = self.build_liked_filter()
            filter_conditions.append(liked_filter)
        elif liked and not store_api_key:
            raise APIKeyError("You must provide an API key to filter by likes")

        if filter_by_user and store_api_key:
            user_data = user_data_var.get()
            if not user_data:
                raise ValueError("No user data")
            filter_conditions.append({"user_created": {"_eq": user_data["id"]}})
        elif filter_by_user and not store_api_key:
            raise APIKeyError("You must provide an API key to filter your components")
        else:
            filter_conditions.append({"private": {"_eq": False}})

        return filter_conditions

    def build_liked_filter(self):
        user_data = user_data_var.get()
        # params["filter"] = json.dumps({"user_created": {"_eq": user_data["id"]}})
        if not user_data:
            raise ValueError("No user data")
        return {"liked_by": {"directus_users_id": {"_eq": user_data["id"]}}}

    async def query_components(
        self,
        api_key: Optional[str] = None,
        sort: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 15,
        fields: Optional[List[str]] = None,
        filter_conditions: Optional[List[Dict[str, Any]]] = None,
        use_api_key: Optional[bool] = False,
    ) -> Tuple[List[ListComponentResponse], Dict[str, Any]]:
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
            "fields": ",".join(fields) if fields is not None else ",".join(self.default_fields),
            "meta": "filter_count",  # !This is DEPRECATED so we should remove it ASAP
        }
        # ?aggregate[count]=likes

        if sort:
            params["sort"] = ",".join(sort)

        # Only public components or the ones created by the user
        # check for "public" or "Public"

        if filter_conditions:
            params["filter"] = json.dumps({"_and": filter_conditions})

        # If not liked, this means we are getting public components
        # so we don't need to risk passing an invalid api_key
        # and getting 401
        api_key = api_key if use_api_key else None
        results, metadata = await self._get(self.components_url, api_key, params)
        if isinstance(results, dict):
            results = [results]

        results_objects = [ListComponentResponse(**result) for result in results]

        return results_objects, metadata

    async def get_liked_by_user_components(self, component_ids: List[str], api_key: str) -> List[str]:
        # Get fields id
        # filter should be "id is in component_ids AND liked_by directus_users_id token is api_key"
        # return the ids
        user_data = user_data_var.get()
        if not user_data:
            raise ValueError("No user data")
        params = {
            "fields": "id",
            "filter": json.dumps(
                {
                    "_and": [
                        {"id": {"_in": component_ids}},
                        {"liked_by": {"directus_users_id": {"_eq": user_data["id"]}}},
                    ]
                }
            ),
        }
        results, _ = await self._get(self.components_url, api_key, params)
        return [result["id"] for result in results]

    # Which of the components is parent of the user's components
    async def get_components_in_users_collection(self, component_ids: List[str], api_key: str):
        user_data = user_data_var.get()
        if not user_data:
            raise ValueError("No user data")
        params = {
            "fields": "id",
            "filter": json.dumps(
                {
                    "_and": [
                        {"user_created": {"_eq": user_data["id"]}},
                        {"parent": {"_in": component_ids}},
                    ]
                }
            ),
        }
        results, _ = await self._get(self.components_url, api_key, params)
        return [result["id"] for result in results]

    async def download(self, api_key: str, component_id: UUID) -> DownloadComponentResponse:
        url = f"{self.components_url}/{component_id}"
        params = {"fields": ",".join(["id", "name", "description", "data", "is_component", "metadata"])}
        if not self.download_webhook_url:
            raise ValueError("DOWNLOAD_WEBHOOK_URL is not set")
        component, _ = await self._get(url, api_key, params)
        await self.call_webhook(api_key, self.download_webhook_url, component_id)
        if len(component) > 1:
            raise ValueError("Something went wrong while downloading the component")
        component_dict = component[0]

        download_component = DownloadComponentResponse(**component_dict)
        # Check if metadata is an empty dict
        if download_component.metadata in [None, {}] and download_component.data is not None:
            # If it is, we need to build the metadata
            try:
                download_component.metadata = process_component_data(download_component.data.get("nodes", []))
            except KeyError:
                raise ValueError("Invalid component data. No nodes found")
        return download_component

    async def upload(self, api_key: str, component_data: StoreComponentCreate) -> CreateComponentResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        component_dict = component_data.model_dump(exclude_unset=True)
        # Parent is a UUID, but the store expects a string
        response = None
        if component_dict.get("parent"):
            component_dict["parent"] = str(component_dict["parent"])

        component_dict = process_tags_for_post(component_dict)
        try:
            # response = httpx.post(self.components_url, headers=headers, json=component_dict)
            # response.raise_for_status()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.components_url, headers=headers, json=component_dict, timeout=self.timeout
                )
                response.raise_for_status()
            component = response.json()["data"]
            return CreateComponentResponse(**component)
        except HTTPError as exc:
            if response:
                try:
                    errors = response.json()
                    message = errors["errors"][0]["message"]
                    if message == "An unexpected error occurred.":
                        # This is a bug in Directus that returns this error
                        # when an error was thrown in the flow
                        message = "You already have a component with this name. Please choose a different name."
                    raise FilterError(message)
                except UnboundLocalError:
                    pass
            raise ValueError(f"Upload failed: {exc}")

    async def update(
        self, api_key: str, component_id: UUID, component_data: StoreComponentCreate
    ) -> CreateComponentResponse:
        # Patch is the same as post, but we need to add the id to the url
        headers = {"Authorization": f"Bearer {api_key}"}
        component_dict = component_data.model_dump(exclude_unset=True)
        # Parent is a UUID, but the store expects a string
        response = None
        if component_dict.get("parent"):
            component_dict["parent"] = str(component_dict["parent"])

        component_dict = process_tags_for_post(component_dict)
        try:
            # response = httpx.post(self.components_url, headers=headers, json=component_dict)
            # response.raise_for_status()
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    self.components_url + f"/{component_id}", headers=headers, json=component_dict, timeout=self.timeout
                )
                response.raise_for_status()
            component = response.json()["data"]
            return CreateComponentResponse(**component)
        except HTTPError as exc:
            if response:
                try:
                    errors = response.json()
                    message = errors["errors"][0]["message"]
                    if message == "An unexpected error occurred.":
                        # This is a bug in Directus that returns this error
                        # when an error was thrown in the flow
                        message = "You already have a component with this name. Please choose a different name."
                    raise FilterError(message)
                except UnboundLocalError:
                    pass
            raise ValueError(f"Upload failed: {exc}")

    async def get_tags(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/items/tags"
        params = {"fields": ",".join(["id", "name"])}
        tags, _ = await self._get(url, api_key=None, params=params)
        return tags

    async def get_user_likes(self, api_key: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/users/me"
        params = {
            "fields": ",".join(["id", "likes"]),
        }
        likes, _ = await self._get(url, api_key, params)
        return likes

    async def get_component_likes_count(self, component_id: str, api_key: Optional[str] = None) -> int:
        url = f"{self.components_url}/{component_id}"

        params = {
            "fields": ",".join(["id", "count(liked_by)"]),
        }
        result, _ = await self._get(url, api_key=api_key, params=params)
        if len(result) == 0:
            raise ValueError("Component not found")
        likes = result[0]["liked_by_count"]
        # likes_by_count is a string
        # try to convert it to int
        try:
            likes = int(likes)
        except ValueError:
            raise ValueError(f"Unexpected value for likes count: {likes}")
        return likes

    async def like_component(self, api_key: str, component_id: str) -> bool:
        # if it returns a list with one id, it means the like was successful
        # if it returns an int, it means the like was removed
        if not self.like_webhook_url:
            raise ValueError("LIKE_WEBHOOK_URL is not set")
        headers = {"Authorization": f"Bearer {api_key}"}
        # response = httpx.post(
        #     self.like_webhook_url,
        #     json={"component_id": str(component_id)},
        #     headers=headers,
        # )

        # response.raise_for_status()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.like_webhook_url,
                json={"component_id": str(component_id)},
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        if response.status_code == 200:
            result = response.json()

            if isinstance(result, list):
                return True
            elif isinstance(result, int):
                return False
            else:
                raise ValueError(f"Unexpected result: {result}")
        else:
            raise ValueError(f"Unexpected status code: {response.status_code}")

    async def get_list_component_response_model(
        self,
        component_id: Optional[str] = None,
        search: Optional[str] = None,
        private: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        is_component: Optional[bool] = None,
        fields: Optional[List[str]] = None,
        filter_by_user: bool = False,
        liked: bool = False,
        store_api_key: Optional[str] = None,
        sort: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 15,
    ):
        async with user_data_context(api_key=store_api_key, store_service=self):
            filter_conditions: List[Dict[str, Any]] = self.build_filter_conditions(
                component_id=component_id,
                search=search,
                private=private,
                tags=tags,
                is_component=is_component,
                filter_by_user=filter_by_user,
                liked=liked,
                store_api_key=store_api_key,
            )

            result: List[ListComponentResponse] = []
            authorized = False
            metadata: Dict = {}
            comp_count = 0
            try:
                result, metadata = await self.query_components(
                    api_key=store_api_key,
                    page=page,
                    limit=limit,
                    sort=sort,
                    fields=fields,
                    filter_conditions=filter_conditions,
                    use_api_key=liked or filter_by_user,
                )
                if metadata:
                    comp_count = metadata.get("filter_count", 0)
            except HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    raise ForbiddenError("You are not authorized to access this public resource") from exc
                elif exc.response.status_code == 401:
                    raise APIKeyError(
                        "You are not authorized to access this resource. Please check your API key."
                    ) from exc
            except Exception as exc:
                raise ValueError(f"Unexpected error: {exc}") from exc
            try:
                if result and not metadata:
                    if len(result) >= limit:
                        comp_count = await self.count_components(
                            api_key=store_api_key,
                            filter_conditions=filter_conditions,
                            use_api_key=liked or filter_by_user,
                        )
                    else:
                        comp_count = len(result)
                elif not metadata:
                    comp_count = 0
            except HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    raise ForbiddenError("You are not authorized to access this public resource")
                elif exc.response.status_code == 401:
                    raise APIKeyError("You are not authorized to access this resource. Please check your API key.")

            if store_api_key:
                # Now, from the result, we need to get the components
                # the user likes and set the liked_by_user to True
                # if any of the components does not have an id, it means
                # we should not update the components

                if not result or any(component.id is None for component in result):
                    authorized = await self.check_api_key(store_api_key)
                else:
                    try:
                        updated_result = await update_components_with_user_data(
                            result, self, store_api_key, liked=liked
                        )
                        authorized = True
                        result = updated_result
                    except Exception:
                        # If we get an error here, it means the user is not authorized
                        authorized = False
        return ListComponentResponseModel(results=result, authorized=authorized, count=comp_count)
