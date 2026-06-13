"""Pre-execution trust verification hook for MCP tool calls.

Consumers implement :class:`TrustVerifier` and pass an instance into
``update_tools()`` or directly onto ``MCPToolsComponent``. When no verifier
is configured, the framework skips the hook entirely with zero overhead.

Decision states
---------------
- ``allow``            - dispatch the tool call normally.
- ``deny``             - block the call; ``PermissionError`` is raised.
- ``warn``             - dispatch the call but emit a warning log entry.
- ``require_approval`` - treated as ``deny`` at the framework level until
                         an interactive approval flow is wired in.

Acceptance contract
-------------------
1. The framework always calls ``verify()`` fresh on every dispatch - it does
   not re-use a previous decision when ``server_uri``, ``tool_name``,
   ``schema_version``, or ``parameters_digest`` differ.
2. ``warn`` is never silently promoted to ``allow``; the warning is always
   logged before the call is dispatched.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

try:
    from typing import Protocol, runtime_checkable
except ImportError:
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]


class TrustState(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class MCPToolCall:
    """Snapshot of a pending MCP tool dispatch passed to :class:`TrustVerifier`.

    All fields that could change the risk profile of the call are included so
    verifiers can make fine-grained decisions and cache logic (in the verifier)
    can be keyed correctly.
    """

    server_uri: str
    tool_name: str
    parameters: dict[str, Any]

    # Optional context - populated when available, empty string / None otherwise.
    server_origin: str = ""
    schema_version: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not self.server_origin and self.server_uri:
            try:
                parsed = urlparse(self.server_uri)
                if parsed.scheme and parsed.netloc:
                    self.server_origin = f"{parsed.scheme}://{parsed.netloc}"
            except ValueError:
                pass

    @property
    def parameters_digest(self) -> str:
        """SHA-256 hex digest of the canonical JSON-serialised parameters."""
        payload = json.dumps(self.parameters, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class TrustDecision:
    """Result returned by a :class:`TrustVerifier`.

    ``decision_id`` is a unique identifier for this decision instance - useful
    for audit logs. ``ttl`` is advisory: it tells the *verifier's own* cache
    how long this decision is valid; the framework never caches decisions.
    """

    state: TrustState
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reason_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl: float | None = None


@runtime_checkable
class TrustVerifier(Protocol):
    """Pluggable trust-verification backend for MCP tool calls.

    Implement this protocol and pass an instance to ``update_tools()`` or
    ``MCPToolsComponent`` to enable pre-dispatch trust checks.

    Example::

        class MyVerifier:
            async def verify(self, call: MCPToolCall) -> TrustDecision:
                if call.server_origin not in TRUSTED_ORIGINS:
                    return TrustDecision(state=TrustState.DENY, reason_code="untrusted_origin")
                return TrustDecision(state=TrustState.ALLOW)
    """

    async def verify(self, call: MCPToolCall) -> TrustDecision:
        """Verify a pending MCP tool call before it is dispatched.

        Args:
            call: Snapshot of the pending tool dispatch.

        Returns:
            A :class:`TrustDecision` indicating whether to allow, deny, warn,
            or require approval for this call.
        """
        ...


async def run_trust_check(
    verifier: TrustVerifier,
    tool_name: str,
    server_uri: str,
    arguments: dict[str, Any],
    *,
    warn_logger: Any = None,
) -> None:
    """Run the trust check for a pending tool dispatch.

    Separated from ``create_tool_coroutine`` so it can be unit-tested without
    importing the full ``util`` module and its heavy dependency chain.

    Args:
        verifier: The :class:`TrustVerifier` to consult.
        tool_name: Name of the MCP tool about to be dispatched.
        server_uri: URI of the MCP server (empty string for stdio).
        arguments: Final arguments that will be sent to the server.
        warn_logger: Optional async callable used to emit the WARN-state log
            message. When ``None``, the warning is silently dropped - callers
            on the async path always supply ``logger.awarning``.

    Raises:
        PermissionError: When the decision state is ``deny`` or
            ``require_approval``.
    """
    call = MCPToolCall(server_uri=server_uri, tool_name=tool_name, parameters=arguments)
    decision = await verifier.verify(call)

    if decision.state in (TrustState.DENY, TrustState.REQUIRE_APPROVAL):
        reason = f" (reason: {decision.reason_code})" if decision.reason_code else ""
        msg = f"MCP tool call '{tool_name}' blocked by trust verifier{reason}"
        raise PermissionError(msg)

    if decision.state == TrustState.WARN and warn_logger is not None:
        reason = decision.reason_code or "no reason given"
        await warn_logger(
            "MCP tool call '%s' allowed with trust warning: %s (decision_id=%s)",
            tool_name,
            reason,
            decision.decision_id,
        )
