import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

import httpx
from httpx import HTTPError, HTTPStatusError
from loguru import logger

from langflow.services.base import Service
from langflow.services.store.schema import (
    CreateComponentResponse,
    DownloadComponentResponse,
    ListComponentResponse,
    StoreComponentCreate,
)
from langflow.services.store.utils import process_tags_for_post

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService

from contextlib import contextmanager
from contextvars import ContextVar

user_data_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar("user_data", default=None)


@contextmanager
def user_data_context(store_service: "StoreService", api_key: Optional[str] = None):
    # Fetch and set user data to the context variable
    if api_key:
        try:
            user_data = store_service._get(f"{store_service.base_url}/users/me", api_key, params={"fields": "id"})
            user_data_var.set(user_data)
        except HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise ValueError("Invalid API key")
    try:
        yield
    finally:
        # Clear the user data from the context variable
        user_data_var.set(None)


class StoreService(Service):
    """This is a service that integrates langflow with the store which
    is a Directus instance. It allows to search, get and post components to
    the store."""

    name = "store_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_url = self.settings_service.settings.STORE_URL
        self.download_webhook_url = self.settings_service.settings.DOWNLOAD_WEBHOOK_URL
        self.like_webhook_url = self.settings_service.settings.LIKE_WEBHOOK_URL
        self.components_url = f"{self.base_url}/items/components"
        self.default_fields = [
            "id",
            "name",
            "description",
            "user_created.first_name",
            "is_component",
            "tags.tags_id.name",
            "tags.tags_id.id",
            "count(liked_by)",
            "count(downloads)",
            "metadata",
            "last_tested_version",
        ]

    # Create a context manager that will use the api key to
    # get the user data and all requests inside the context manager
    # will make a property return that data
    # Without making the request multiple times

    async def _get(
        self, url: str, api_key: Optional[str] = None, params: Optional[Dict[str, Any]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Utility method to perform GET requests."""
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            headers = {}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
            except HTTPError as exc:
                raise exc
            except Exception as exc:
                raise ValueError(f"GET failed: {exc}")
        return response.json()["data"]

    async def call_webhook(self, api_key: str, webhook_url: str, component_id: UUID) -> None:
        # The webhook is a POST request with the data in the body
        # For now we are calling it just for testing
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, headers=headers, json={"component_id": str(component_id)})
                response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise exc
        except Exception as exc:
            logger.debug(f"Webhook failed: {exc}")

    def build_tags_filter(self, tags: List[str]):
        tags_filter = {"tags": {"_and": []}}
        for tag in tags:
            tags_filter["tags"]["_and"].append({"_some": {"tags_id": {"name": {"_eq": tag}}}})
        return tags_filter

    async def count_components(
        self,
        filter_conditions: List[Dict[str, Any]],
        api_key: Optional[str] = None,
    ) -> int:
        params = {"aggregate": json.dumps({"count": "*"})}
        if filter_conditions:
            params["filter"] = json.dumps({"_and": filter_conditions})

        results = await self._get(self.components_url, api_key, params)
        return int(results[0].get("count", 0))

    @staticmethod
    def build_search_filter_conditions(query: str):
        # instead of build the param ?search=query, we will build the filter
        # that will use _icontains (case insensitive)
        conditions = {"_or": []}
        conditions["_or"].append({"name": {"_icontains": query}})
        conditions["_or"].append({"description": {"_icontains": query}})
        conditions["_or"].append({"tags": {"tags_id": {"name": {"_icontains": query}}}})
        return conditions

    def build_filter_conditions(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_component: Optional[bool] = None,
        liked: bool = False,
        api_key: Optional[str] = None,
        filter_by_user: Optional[bool] = False,
    ):
        filter_conditions = []

        if search is not None:
            search_conditions = self.build_search_filter_conditions(search)
            filter_conditions.append(search_conditions)

        if status:
            filter_conditions.append({"status": {"_eq": status}})

        if tags:
            tags_filter = self.build_tags_filter(tags)
            filter_conditions.append(tags_filter)

        if is_component is not None:
            filter_conditions.append({"is_component": {"_eq": is_component}})

        if filter_by_user:
            user_data = user_data_var.get()
            if not user_data:
                raise ValueError("No user data")
            filter_conditions.append({"user_created": {"_eq": user_data["id"]}})

        liked_filter = self.build_liked_filter(liked, api_key)
        filter_conditions.append(liked_filter)

        return filter_conditions

    def build_liked_filter(self, liked: bool, api_key: Optional[str] = None):
        if liked and not api_key:
            raise ValueError("No API key provided")

        if liked and api_key:
            user_data = user_data_var.get()
            # params["filter"] = json.dumps({"user_created": {"_eq": user_data["id"]}})
            if not user_data:
                raise ValueError("No user data")
            return {"liked_by": {"_eq": user_data["id"]}}
        else:
            return {"status": {"_in": ["public", "Public"]}}

    async def query_components(
        self,
        api_key: Optional[str] = None,
        sort: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 15,
        fields: Optional[List[str]] = None,
        filter_conditions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ListComponentResponse]:
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
            "fields": ",".join(fields) if fields else ",".join(self.default_fields),
        }
        # ?aggregate[count]=likes

        if sort:
            params["sort"] = ",".join(sort)

        # Only public components or the ones created by the user
        # check for "public" or "Public"

        if filter_conditions:
            params["filter"] = json.dumps({"_and": filter_conditions})

        results = await self._get(self.components_url, api_key, params)
        results_objects = [ListComponentResponse(**component) for component in results]
        # Flatten the tags
        # for component in results_objects:
        #     if component.tags:
        #         component.tags = [tags_id.tags_id for tags_id in component.tags]
        return results_objects

    async def get_liked_by_user_components(self, component_ids: List[UUID], api_key: str) -> List[UUID]:
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
        results = await self._get(self.components_url, api_key, params)
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
        results = await self._get(self.components_url, api_key, params)
        return [result["id"] for result in results]

    async def download(self, api_key: str, component_id: UUID) -> DownloadComponentResponse:
        url = f"{self.components_url}/{component_id}"
        params = {"fields": ",".join(["id", "name", "description", "data", "is_component"])}

        component = await self._get(url, api_key, params)
        await self.call_webhook(api_key, self.download_webhook_url, component_id)

        return DownloadComponentResponse(**component)

    async def upload(self, api_key: str, component_data: StoreComponentCreate) -> CreateComponentResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        component_dict = component_data.dict(exclude_unset=True)
        # Parent is a UUID, but the store expects a string
        response = None
        if component_dict.get("parent"):
            component_dict["parent"] = str(component_dict["parent"])

        component_dict = process_tags_for_post(component_dict)
        try:
            # response = httpx.post(self.components_url, headers=headers, json=component_dict)
            # response.raise_for_status()
            async with httpx.AsyncClient() as client:
                response = await client.post(self.components_url, headers=headers, json=component_dict)
                response.raise_for_status()
            component = response.json()["data"]
            return CreateComponentResponse(**component)
        except HTTPError as exc:
            if response:
                try:
                    errors = response.json()
                    message = errors["errors"][0]["message"]
                    raise ValueError(message)
                except UnboundLocalError:
                    pass
            raise ValueError(f"Upload failed: {exc}")

    async def get_tags(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/items/tags"
        params = {"fields": ",".join(["id", "name"])}
        tags = await self._get(url, api_key=None, params=params)
        return tags

    async def get_user_likes(self, api_key: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/users/me"
        params = {
            "fields": ",".join(["id", "likes"]),
        }
        likes = await self._get(url, api_key, params)
        return likes

    async def get_component_likes_count(self, api_key: str, component_id: str) -> int:
        url = f"{self.components_url}/{component_id}"

        params = {
            "fields": ",".join(["id", "count(liked_by)"]),
        }
        result = await self._get(url, api_key, params)
        if len(result) == 0:
            raise ValueError("Component not found")
        likes = result["liked_by_count"]
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
