from pydantic import BaseModel


class RunPayload(BaseModel):
    runIsWebhook: bool = False
    runSeconds: int
    runSuccess: bool
    runErrorMessage: str = ""


class ShutdownPayload(BaseModel):
    timeRunning: int


class VersionPayload(BaseModel):
    package: str
    version: str
    platform: str
    python: str
    arch: str
    autoLogin: bool
    cacheType: str
    backendOnly: bool


class PlaygroundPayload(BaseModel):
    playgroundSeconds: int
    playgroundComponentCount: int | None = None
    playgroundSuccess: bool
    playgroundErrorMessage: str = ""


class ComponentPayload(BaseModel):
    componentName: str
    componentSeconds: int
    componentSuccess: bool
    componentErrorMessage: str | None = None
