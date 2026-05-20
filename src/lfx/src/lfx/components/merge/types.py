from __future__ import annotations

from typing import Literal

try:
    from typing import NotRequired, TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import NotRequired, TypedDict


class MergeConnector(TypedDict):
    name: str
    slug: str


class MergeToolPack(TypedDict):
    id: str
    name: str
    description: NotRequired[str]
    connectors: NotRequired[list[MergeConnector]]


class MergeSharedCredentialGroup(TypedDict, total=False):
    origin_company_id: str
    origin_company_name: str


class MergeRegisteredUser(TypedDict, total=False):
    id: str
    origin_user_id: str
    origin_user_name: str
    shared_credential_group: MergeSharedCredentialGroup
    user_type: str
    authenticated_connectors: list[str]
    is_test: bool


class McpJsonSchemaProperty(TypedDict, total=False):
    type: str
    description: str
    enum: list[str]
    items: "McpJsonSchemaProperty"
    properties: dict[str, "McpJsonSchemaProperty"]
    required: list[str]


class McpToolInputSchema(TypedDict, total=False):
    type: Literal["object"]
    properties: dict[str, McpJsonSchemaProperty]
    required: list[str]


class McpTool(TypedDict):
    name: str
    description: NotRequired[str]
    inputSchema: McpToolInputSchema


class McpResultContent(TypedDict, total=False):
    type: str
    text: str


class McpJsonRpcResult(TypedDict, total=False):
    tools: list[McpTool]
    content: list[McpResultContent]
    isError: bool


class McpJsonRpcError(TypedDict, total=False):
    code: int
    message: str
    data: object


class McpJsonRpcRequest(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    method: str
    params: dict[str, object]


class McpJsonRpcResponse(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    result: McpJsonRpcResult
    error: McpJsonRpcError
