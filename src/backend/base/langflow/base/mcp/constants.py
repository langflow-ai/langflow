"""Shared constants for the MCP client implementations.

Keeping protocol version strings in a single location avoids accidental
mismatches and magic values sprinkled throughout the codebase.
"""

# Supported MCP protocol versions
PROTOCOL_V_2024_11_05 = "2024-11-05"
PROTOCOL_V_2025_03_26 = "2025-03-26"

# Latest protocol the client natively understands
LATEST_PROTOCOL_VERSION = PROTOCOL_V_2025_03_26
