from fastapi_pagination import Page

from langflow.helpers.base_model import BaseModel
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import ProjectRead


class FolderWithPaginatedFlows(BaseModel):
    folder: ProjectRead
    flows: Page[Flow]
