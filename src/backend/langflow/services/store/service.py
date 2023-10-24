from datetime import datetime
from langflow.services.base import Service
from typing import TYPE_CHECKING, List, Dict, Any, Optional
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
        sort: Optional[List[str]] = ["-likes"],
        fields: Optional[List[str]] = None,
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

        results = self._get(self.components_url, api_key, params)
        return [ComponentResponse(**component) for component in results]

    def list_components(
        self,
        api_key: str,
        page: int = 1,
        limit: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[ListComponentResponse]:
        params = {"page": page, "limit": limit}
        # ?aggregate[count]=likes
        params["fields"] = (
            ",".join(fields)
            if fields
            else ",".join(["id", "name", "description", "count(likes)", "is_component"])
        )

        results = self._get(self.components_url, api_key, params)
        return [ListComponentResponse(**component) for component in results]

    def download(self, api_key: str, id: str) -> DownloadComponentResponse:
        url = f"{self.components_url}/{id}"
        params = {
            "fields": ",".join(["id", "name", "description", "data", "is_component"])
        }
        component = self._get(url, api_key, params)
        return DownloadComponentResponse(**component)

    def upload(
        self, api_key: str, component_data: StoreComponentCreate
    ) -> ComponentResponse:
        headers = {"Authorization": f"Bearer {api_key}"}
        component_dict = component_data.dict(exclude_unset=True)
        # Parent is a UUID, but the store expects a string
        if component_dict.get("parent"):
            component_dict["parent"] = str(component_dict["parent"])
        try:
            response = httpx.post(
                self.components_url, headers=headers, json=component_dict
            )
            response.raise_for_status()
            component = response.json()["data"]
            return ComponentResponse(**component)
        except HTTPError as exc:
            raise ValueError(f"Upload failed: {exc}")
