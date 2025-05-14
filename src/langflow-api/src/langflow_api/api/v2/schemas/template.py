from pydantic import BaseModel

class UpdateTemplateRequest(BaseModel):
    template: dict


