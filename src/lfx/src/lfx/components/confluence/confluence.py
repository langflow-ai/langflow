from langchain_community.document_loaders import ConfluenceLoader
from langchain_community.document_loaders.confluence import ContentFormat

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class ConfluenceComponent(Component):
    display_name = "Confluence"
    description = "Confluence wiki collaboration platform"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/document_loaders/confluence/"
    trace_type = "tool"
    icon = "Confluence"
    name = "Confluence"

    inputs = [
        StrInput(
            name="url",
            display_name="Site URL",
            required=True,
            info="The base URL of the Confluence Space. Example: https://<company>.atlassian.net/wiki.",
        ),
        StrInput(
            name="username",
            display_name="Username",
            required=True,
            info="Atlassian User E-mail. Example: email@example.com",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            info="Atlassian Key. Create at: https://id.atlassian.com/manage-profile/security/api-tokens",
        ),
        StrInput(name="space_key", display_name="Space Key", required=True),
        BoolInput(name="cloud", display_name="Use Cloud?", required=True, value=True, advanced=True),
        DropdownInput(
            name="content_format",
            display_name="Content Format",
            options=[
                ContentFormat.EDITOR.value,
                ContentFormat.EXPORT_VIEW.value,
                ContentFormat.ANONYMOUS_EXPORT_VIEW.value,
                ContentFormat.STORAGE.value,
                ContentFormat.VIEW.value,
            ],
            value=ContentFormat.STORAGE.value,
            required=True,
            advanced=True,
            info="Specify content format, defaults to ContentFormat.STORAGE",
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            required=False,
            value=1000,
            advanced=True,
            info="Maximum number of pages to retrieve in total, defaults 1000",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    def build_confluence(self) -> ConfluenceLoader:
        content_format = ContentFormat(self.content_format)
        return ConfluenceLoader(
            url=self.url,
            username=self.username,
            api_key=self.api_key,
            cloud=self.cloud,
            space_key=self.space_key,
            content_format=content_format,
            max_pages=self.max_pages,
        )

    def load_documents(self) -> list[Data]:
        confluence = self.build_confluence()
        documents = confluence.load()
        data = [Data.from_document(doc) for doc in documents]  # Using the from_document method of Data
        self.status = data
        return data
