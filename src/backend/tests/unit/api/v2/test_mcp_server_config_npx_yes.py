"""Validator behavior around `npx -y <package>` patterns.

Why this exists: the default `shell-execution` MCP server is now backed by
`wonderwhy-er/desktop-commander`, which is an npm package distributed via npx.
Launching it requires `npx -y @wonderwhy-er/desktop-commander@latest` — but
`-y`/`--yes` was previously rejected by the validator as a dangerous keyword.

We replace that blanket rejection with a strict, package-allowlisted exception:
`-y`/`--yes` is allowed iff the rest of the invocation matches
`npx -y <pkg-on-allowlist>`, either directly or inside an approved shell-wrapper.

Every other usage of `-y`/`--yes` MUST continue to be rejected. These tests
cover both the new accepts and every regression vector we audited.
"""

import pytest
from langflow.api.v2.schemas import MCPServerConfig
from pydantic import ValidationError

# Pinned name strings of the only npm packages we ship as default MCP servers
# that legitimately require `npx -y` to launch.
APPROVED_PKG = "@wonderwhy-er/desktop-commander@latest"
APPROVED_PKG_NO_TAG = "@wonderwhy-er/desktop-commander"
DISALLOWED_PKG = "@evil/random-pkg"


class TestAcceptsApprovedNpxYesPattern:
    def test_should_accept_npx_yes_with_allowed_package(self):
        """Slice A1: the canonical launch path for desktop-commander must validate."""
        MCPServerConfig.model_validate({"command": "npx", "args": ["-y", APPROVED_PKG]})


class TestRejectsDisallowedPackage:
    def test_should_reject_when_npx_yes_targets_disallowed_package(self):
        """Slice A2 / Threat T1: bypass via arbitrary npm package must fail.

        The whole point of the allowlist is that `-y` is meaningful only for the
        specific packages we ship — never as a generic escape hatch.
        """
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "npx", "args": ["-y", DISALLOWED_PKG]})


class TestAcceptsDoubleDashYesVariant:
    def test_should_accept_npx_double_dash_yes_with_allowed_package(self):
        """Slice A3: --yes is the long-form alias of -y; must be treated identically."""
        MCPServerConfig.model_validate({"command": "npx", "args": ["--yes", APPROVED_PKG]})

    def test_should_reject_npx_double_dash_yes_with_disallowed_package(self):
        """Slice A3 / Threat T1: same allowlist enforcement applies to --yes."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "npx", "args": ["--yes", DISALLOWED_PKG]})


class TestRejectsYesFlagOutsideNpx:
    def test_should_reject_yes_flag_with_python_command(self):
        """Slice A4 / Threat T3: -y must never be allowed for Python (or any non-npx)."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "python", "args": ["-y", "anything"]})

    def test_should_reject_yes_flag_with_bash_command_no_dash_c(self):
        """Slice A5 / Threat T3: bare -y rejected on bash without -c.

        Bash without -c is not a shell-wrapper context; a bare -y in args is
        rejected the same as for python.
        """
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "bash", "args": ["-y", "anything"]})


class TestRejectsBareYesFlag:
    def test_should_reject_bare_yes_flag_with_npx(self):
        """Slice A6 / Threat T9: 'npx -y' alone (no package) must fail."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "npx", "args": ["-y"]})


class TestRejectsWrongOrder:
    def test_should_reject_when_yes_flag_does_not_precede_package(self):
        """Slice A7 / Threat T4: ['<pkg>', '-y'] must fail — strict ordering."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "npx", "args": [APPROVED_PKG, "-y"]})

    def test_should_reject_when_extra_args_follow_npx_yes_pkg(self):
        """Slice A7 / Threat T8: trailing args must be rejected (length must be exactly 2)."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "npx", "args": ["-y", APPROVED_PKG, "--extra"]})


class TestShellWrapperAcceptsApprovedNpxYes:
    """Shell-wrapper variants must work too — Windows uses cmd /c, Unix uses sh -c.

    The wrapped command is a single quoted string carrying `npx -y <approved-pkg>`.
    """

    def test_should_accept_sh_dash_c_with_npx_yes_approved_package(self):
        """Slice A8: legitimate Unix-style wrapper invocation."""
        MCPServerConfig.model_validate({"command": "sh", "args": ["-c", f"npx -y {APPROVED_PKG}"]})

    def test_should_accept_bash_dash_c_with_npx_yes_approved_package(self):
        """Slice A8: bash flavor of the same."""
        MCPServerConfig.model_validate({"command": "bash", "args": ["-c", f"npx -y {APPROVED_PKG}"]})

    def test_should_accept_cmd_slash_c_with_npx_yes_approved_package(self):
        """Slice A10: Windows-style wrapper invocation."""
        MCPServerConfig.model_validate({"command": "cmd", "args": ["/c", f"npx -y {APPROVED_PKG}"]})


class TestShellWrapperRejectsLoophole:
    """Closes the historical shell-wrapper loophole.

    The previous validator inspected wrapper args as a single string and never
    tokenized the wrapped command. Threat T2: attacker chooses any npm package
    and quotes it inside the wrapped string. Current behavior: passes because
    the whole string '-y <pkg>' is one arg and never matches DANGEROUS_KEYWORDS
    by exact equality. After fix: tokenize the wrapped string with shlex and
    re-apply the npx-yes pattern check.
    """

    def test_should_reject_sh_dash_c_with_npx_yes_disallowed_package(self):
        """Slice A9: the canonical loophole — wrapped npx -y of any package."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "sh", "args": ["-c", f"npx -y {DISALLOWED_PKG}"]})

    def test_should_reject_bash_dash_c_with_npx_yes_disallowed_package(self):
        """Slice A9: bash variant."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "bash", "args": ["-c", f"npx -y {DISALLOWED_PKG}"]})

    def test_should_reject_cmd_slash_c_with_npx_yes_disallowed_package(self):
        """Slice A9: Windows variant."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "cmd", "args": ["/c", f"npx -y {DISALLOWED_PKG}"]})


class TestRejectsStrayYesFlagInShellWrapper:
    """Threat T5: -y must not appear loose in shell-wrapper args.

    The wrapped command (single string after -c/'/c') is the ONLY place where
    -y can legitimately appear, and only when it sits inside the approved npx
    pattern. Tests use a wrapped command that itself passes existing checks
    (`npx <pkg>`) so the rejection must come from the new top-level guard,
    not from collateral protection.
    """

    def test_should_reject_stray_yes_flag_after_wrapped_command(self):
        """Slice A11: -y is the third arg, outside the wrapped command string."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "sh", "args": ["-c", f"npx {APPROVED_PKG}", "-y"]})

    def test_should_reject_stray_double_dash_yes_after_wrapped_command(self):
        """Slice A11: same with --yes."""
        with pytest.raises(ValidationError):
            MCPServerConfig.model_validate({"command": "cmd", "args": ["/c", f"npx {APPROVED_PKG}", "--yes"]})
