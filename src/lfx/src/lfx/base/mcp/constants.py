import re

MAX_MCP_SERVER_NAME_LENGTH = 30
MAX_MCP_TOOL_NAME_LENGTH = 30

GLOBAL_VARIABLE_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*\}\}")
