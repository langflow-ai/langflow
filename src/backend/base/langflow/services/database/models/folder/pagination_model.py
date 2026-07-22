from fastapi_pagination import Page

from langflow.helpers.base_model import BaseModel
from langflow.services.database.models.flow.model import FlowRead, FlowSummary
from langflow.services.database.models.folder.model import FolderRead


class FolderWithPaginatedFlows(BaseModel):
    folder: FolderRead
    flows: Page[FlowRead]


class FolderWithPaginatedFlowSummaries(BaseModel):
    folder: FolderRead
    flows: Page[FlowSummary]
