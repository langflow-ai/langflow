from pydantic import BaseModel, ConfigDict
from langflow_api.api.v2.schemas.flow import FlowCreate, FlowRead

class CustomComponentRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    code: str
    frontend_node: dict | None = None

class CustomComponentResponse(BaseModel):
    data: dict
    type: str

class UpdateCustomComponentRequest(CustomComponentRequest):
    field: str
    field_value: str | int | float | bool | dict | list | None = None
    template: dict
    tool_mode: bool = False

    def get_template(self):
        from langflow.schema import dotdict
        return dotdict(self.template)

class CustomComponentResponseError(BaseModel):
    detail: str
    traceback: str

class ComponentListCreate(BaseModel):
    flows: list[FlowCreate]

class ComponentListRead(BaseModel):
    flows: list[FlowRead]



