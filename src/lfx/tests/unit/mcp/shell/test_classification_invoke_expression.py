"""Security tests for PowerShell ``Invoke-Expression`` and ``Invoke-Command``.

These cmdlets are the PowerShell equivalent of ``eval`` / ``bash -c``:
they take an arbitrary string and execute it as code. The destructive
payload inside the string is never visible to our static validators,
so the only safe stance is to refuse them at classification time
(fail-closed) — exactly the same treatment we already give to
``eval``, ``bash -c``, ``sh -c``, ``python -c`` etc.

``Invoke-WebRequest`` and ``Invoke-RestMethod`` are legitimate network
cmdlets and remain classified as NETWORK via the verb-prefix rule.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    "command",
    [
        'Invoke-Expression "Remove-Item C:\\foo"',
        'Invoke-Expression "format C:"',
        "invoke-expression $payload",
        "INVOKE-EXPRESSION $code",  # case-insensitive
        # ``iex`` and ``IEX`` already happen to fall back to UNKNOWN because
        # they don't match the Verb-Noun regex, but we lock that in with a
        # test so a future refactor doesn't silently change behaviour.
        "iex $code",
        "IEX $code",
        "Iex 'Remove-Item C:\\'",
        # ``Invoke-Command -ScriptBlock { ... }`` is also code-injection.
        "Invoke-Command -ScriptBlock { Remove-Item C:\\ }",
        "invoke-command -ComputerName remote -ScriptBlock { format C: }",
    ],
)
def test_should_classify_invoke_expression_family_as_unknown(command: str):
    """eval-style cmdlets must be UNKNOWN -> rejected by the pipeline."""
    assert classify_command(command) == CommandIntent.UNKNOWN


@pytest.mark.parametrize(
    "command",
    [
        # Legitimate network usage — verb-prefix ``invoke`` -> NETWORK.
        "Invoke-WebRequest https://example.com",
        "Invoke-RestMethod https://api.example.com",
        "invoke-webrequest -Uri https://x",
    ],
)
def test_should_keep_legitimate_invoke_cmdlets_as_network(command: str):
    """We must not regress: Invoke-WebRequest stays a network cmdlet."""
    assert classify_command(command) == CommandIntent.NETWORK
