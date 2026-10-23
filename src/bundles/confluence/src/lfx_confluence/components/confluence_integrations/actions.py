"""Explicit page actions with approved spaces and optimistic content versions."""

from lfx.io import IntInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_confluence.base import ConfluenceActionComponent
from lfx_confluence.manifest import connection_input
from lfx_confluence.schema import (
    MAX_VERSION,
    approved_space,
    invalid,
    list_params,
    numeric_id,
    page_data,
    page_list,
    text,
)


def space_input():
    return MessageTextInput(
        name="space_id",
        display_name="Space ID",
        required=True,
        info="An operator-approved numeric Confluence space ID.",
    )


class ConfluenceSearchPagesComponent(ConfluenceActionComponent):
    display_name = "Confluence Search Pages"
    description = "List published pages in one approved space, optionally matching an exact title."
    name = "ConfluenceSearchPages"
    capability_id = "confluence.page.search"
    inputs = [
        connection_input(capability_id),
        space_input(),
        MessageTextInput(name="title", display_name="Exact Title"),
        MessageTextInput(name="cursor", display_name="Next Page Cursor", advanced=True),
    ]
    outputs = [Output(display_name="Pages", name="pages", method="search_pages")]

    async def search_pages(self) -> Data:
        space = approved_space(self.space_id)
        title = getattr(self, "title", "") or ""
        result = await self.perform(
            "GET",
            "/wiki/api/v2/pages",
            params=list_params(space, title=title, cursor=getattr(self, "cursor", "") or ""),
        )
        pages, cursor = page_list(result, space=space)
        if title and any(page["title"] != title for page in pages):
            msg = "Confluence returned a page outside the exact title filter."
            raise invalid(msg)
        return Data(data={"pages": pages, "next_cursor": cursor})


class ConfluenceReadPageComponent(ConfluenceActionComponent):
    display_name = "Confluence Read Page"
    description = "Read one current page and its storage body from an approved space."
    name = "ConfluenceReadPage"
    capability_id = "confluence.page.read"
    inputs = [
        connection_input(capability_id),
        space_input(),
        MessageTextInput(name="page_id", display_name="Page ID", required=True),
    ]
    outputs = [Output(display_name="Page", name="page", method="read_page")]

    async def read_page(self) -> Data:
        space, identifier = approved_space(self.space_id), numeric_id(self.page_id)
        result = await self.perform(
            "GET", f"/wiki/api/v2/pages/{identifier}", params={"body-format": "storage", "status": "current"}
        )
        return Data(data=page_data(result, space=space, identifier=identifier, include_body=True))


class ConfluenceCreatePageComponent(ConfluenceActionComponent):
    display_name = "Confluence Create Page"
    description = "Publish one page with a storage-format body in an approved space."
    name = "ConfluenceCreatePage"
    capability_id = "confluence.page.create"
    inputs = [
        connection_input(capability_id),
        space_input(),
        MessageTextInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body_storage", display_name="Storage Body", required=True),
        MessageTextInput(name="parent_id", display_name="Parent Page ID", advanced=True),
    ]
    outputs = [Output(display_name="Page", name="page", method="create_page")]

    async def create_page(self) -> Data:
        space = approved_space(self.space_id)
        body = {
            "spaceId": space,
            "status": "current",
            "title": text(self.title, maximum=255),
            "body": {"representation": "storage", "value": text(self.body_storage, maximum=524288, required=False)},
        }
        parent = getattr(self, "parent_id", "")
        if parent:
            parent = numeric_id(parent)
            existing = await self.perform("GET", f"/wiki/api/v2/pages/{parent}", params={"status": "current"})
            page_data(existing, space=space, identifier=parent)
            body["parentId"] = parent
        result = await self.perform("POST", "/wiki/api/v2/pages", body=body, write=True)
        return Data(data=page_data(result, space=space))


class ConfluenceUpdatePageComponent(ConfluenceActionComponent):
    display_name = "Confluence Update Page"
    description = "Replace a published page only when its current version matches the expected version."
    name = "ConfluenceUpdatePage"
    capability_id = "confluence.page.update"
    inputs = [
        connection_input(capability_id),
        space_input(),
        MessageTextInput(name="page_id", display_name="Page ID", required=True),
        IntInput(name="expected_version", display_name="Expected Current Version", required=True, value=1),
        MessageTextInput(name="title", display_name="Title", required=True),
        MultilineInput(name="body_storage", display_name="Storage Body", required=True),
    ]
    outputs = [Output(display_name="Page", name="page", method="update_page")]

    async def update_page(self) -> Data:
        space, identifier = approved_space(self.space_id), numeric_id(self.page_id)
        expected = self.expected_version
        if type(expected) is not int or not 1 <= expected < MAX_VERSION:
            msg = "Provide the expected positive current page version."
            raise invalid(msg)
        title = text(self.title, maximum=255)
        storage = text(self.body_storage, maximum=524288, required=False)
        current = page_data(
            await self.perform("GET", f"/wiki/api/v2/pages/{identifier}", params={"status": "current"}),
            space=space,
            identifier=identifier,
        )
        if current["version"] != expected:
            msg = "The page changed. Read its current version before submitting another update."
            raise invalid(msg)
        result = await self.perform(
            "PUT",
            f"/wiki/api/v2/pages/{identifier}",
            body={
                "id": identifier,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": storage},
                "version": {"number": expected + 1},
            },
            write=True,
        )
        updated = page_data(result, space=space, identifier=identifier)
        if updated["version"] != expected + 1:
            msg = "Confluence returned an unexpected updated page version."
            raise invalid(msg)
        return Data(data=updated)
