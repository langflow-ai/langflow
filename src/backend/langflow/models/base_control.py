from pydantic import BaseModel
from datetime import datetime


class BaseControl(BaseModel):
    created_at: datetime
    updated_at: datetime
