from datetime import datetime
import json
from uuid import UUID
from langflow.services.base import Service
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Union
import httpx

from httpx import HTTPError
from langflow.services.store.schema import (
    ComponentResponse,
    DownloadComponentResponse,
    ListComponentResponse,
    StoreComponentCreate,
)

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class StoreService(Service):
    """This is a service that integrates langflow with the store which
    is a Directus instance. It allows to search, get and post components to
    the store."""

    name = "store_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_url = self.settings_service.settings.STORE_URL
        self.webhook_url = self.settings_service.settings.DOWNLOAD_WEBHOOK_URL
        self.components_url = f"{self.base_url}/items/components"

    def _get(
        self, url: str, api_key: str, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Utility method to perform GET requests."""
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            headers = {}
        try:
            response = httpx.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()["data"]
        except HTTPError as exc:
            raise exc
        except Exception as exc:
            raise ValueError(f"GET failed: {exc}")

    def call_webhook(self, api_key: str, webhook_url: str, component_id: UUID) -> None:
        # The webhook is a POST request with the data in the body
        # For now we are calling it just for testing
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = httpx.post(
                webhook_url, headers=headers, json={"component_id": str(component_id)}
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise exc

    def search(
        self,
        api_key: Optional[str],
        query: str,
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort: Optional[List[str]] = ["-count(liked_by)"],
        fields: Optional[List[str]] = None,
        filter_by_user: bool = False,
    ) -> List[ComponentResponse]:
        # ?sort=sort,-date_created,author.name

        # // or

        # ?sort[]=sort
        # &sort[]=-date_created
        # &sort[]=-author.name
        params = {
            "search": query,
            "page": page,
            "limit": limit,
        }

        if status:
            params["filter[status]"] = status

        if tags:
            params["filter[tags][_in]"] = ",".join(tags)

        if date_from:
            params["filter[date_updated][_gte]"] = date_from.isoformat()

        if date_to:
            params["filter[date_updated][_lte]"] = date_to.isoformat()

        if sort:
            params["sort"] = ",".join(sort)

        if fields:
            params["fields"] = ",".join(fields)

        if filter_by_user:
            params["deep"] = json.dumps(
                {
                    "components": {
                        "_filter": {"user_created": {"token": {"_eq": api_key}}}
                    }
                }
            )
        else:
            params["filter"] = json.dumps({"status": {"_eq": "public"}})

        results = self._get(self.components_url, api_key, params)
        return [ComponentResponse(**component) for component in results]

    def count_components(
        self,
        api_key: Optional[str] = None,
        filter_by_user: bool = False,
    ) -> int:
        params = {"aggregate": json.dumps({"count": "*"})}
        if filter_by_user:
            params["deep"] = json.dumps(
                {
                    "components": {
                        "_filter": {"user_created": {"token": {"_eq": api_key}}}
                    }
                }
            )
        else:
            params["filter"] = json.dumps({"status": {"_in": ["public", "Public"]}})
        results = self._get(self.components_url, api_key, params)
        return results[0].get("count", 0)

    def query_components(
        self,
        api_key: str,
        page: int = 1,
        limit: int = 15,
        fields: Optional[List[str]] = None,
        filter_by_user: bool = False,
    ) -> Union[List[ListComponentResponse], List[Dict[str, int]]]:
        params = {"page": page, "limit": limit}
        # ?aggregate[count]=likes
        params["fields"] = (
            ",".join(fields)
            if fields
            else ",".join(
                ["id", "name", "description", "count(liked_by)", "is_component"]
            )
        )
        # Only public components or the ones created by the user
        # check for "public" or "Public"

        if filter_by_user:
            params["deep"] = json.dumps(
                {
                    "components": {
                        "_filter": {"user_created": {"token": {"_eq": api_key}}}
                    }
                }
            )
        else:
            params["filter"] = params["filter"] = json.dumps(
                {"status": {"_in": ["public", "Public"]}}
            )

        results = self._get(self.components_url, api_key, params)
        return [ListComponentResponse(**component) for component in results]

    def download(self, api_key: str, component_id: str) -> DownloadComponentResponse:
        url = f"{self.components_url}/{component_id}"
        params = {
            "fields": ",".join(["id", "name", "description", "data", "is_component"])
        }

        component = self._get(url, api_key, params)
        self.call_webhook(api_key, self.webhook_url, component_id)

        return DownloadComponentResponse(**component)

    def upload(
        self, api_key: str, component_data: StoreComponentCreate
    ) -> ComponentResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        component_dict = component_data.dict(exclude_unset=True)
        # Parent is a UUID, but the store expects a string
        response = None
        if component_dict.get("parent"):
            component_dict["parent"] = str(component_dict["parent"])
        try:
            response = httpx.post(
                self.components_url, headers=headers, json=component_dict
            )
            response.raise_for_status()
            # ! If the user does not have permission to a certain field
            # the request returns 204 and no data
            try:
                component = response.json()["data"]
                return ComponentResponse(**component)
            except json.JSONDecodeError:
                return ComponentResponse(**component_dict)
        except HTTPError as exc:
            if response:
                try:
                    errors = response.json()
                    message = errors["errors"][0]["message"]
                    raise ValueError(message)
                except UnboundLocalError:
                    pass
            raise ValueError(f"Upload failed: {exc}")

    def get_tags(self, api_key: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/items/tags"
        params = {"fields": ",".join(["id", "name"])}
        tags = self._get(url, api_key, params)
        return tags
