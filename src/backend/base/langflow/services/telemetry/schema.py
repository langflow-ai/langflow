from pydantic import BaseModel


class RunPayload(BaseModel):
    IsWebhook: bool = False
    seconds: int
    success: bool
    errorMessage: str = ""


class ShutdownPayload(BaseModel):
    timeRunning: int


class VersionPayload(BaseModel):
    version: str
    platform: str
    python: str
    arch: str
    autoLogin: bool
    cacheType: str
    backendOnly: bool


class PlaygroundPayload(BaseModel):
    seconds: int
    componentCount: int | None = None
    success: bool
    errorMessage: str = ""


class ComponentPayload(BaseModel):
    name: str
    seconds: int
    success: bool
    errorMessage: str
