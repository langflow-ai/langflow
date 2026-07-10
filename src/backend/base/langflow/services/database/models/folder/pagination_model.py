from fastapi_pagination import Page
from lfx.services.database.models.flow import FlowRead
from lfx.services.database.models.folder import FolderRead

from langflow.helpers.base_model import BaseModel


class FolderWithPaginatedFlows(BaseModel):
    folder: FolderRead
    flows: Page[FlowRead]
