"""Tests for the installer protocol — the contract every installer must honor.

The protocol is small on purpose:
  - install(consent_callback) -> InstallOutcome   (exactly this signature)
  - InstallOutcome is a typed result with a status enum + optional message

Why a Protocol (PEP 544) and not an ABC: installers live in different modules and
should not have to import a base class. A structural Protocol gives us the LSP
guarantee without coupling.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# InstallStatus enum — finite, ordered set of outcomes
# ---------------------------------------------------------------------------


class TestInstallStatus:
    @pytest.mark.parametrize(
        "name",
        [
            "SUCCESS",
            "DECLINED",
            "FAILED",
            "UNSUPPORTED",
            "ALREADY_INSTALLED",
        ],
    )
    def test_should_expose_canonical_status(self, name):
        from lfx.services.local_model.installers.protocol import InstallStatus

        assert hasattr(InstallStatus, name)

    def test_status_values_should_be_distinct(self):
        from lfx.services.local_model.installers.protocol import InstallStatus

        # Why distinct values: callers branch on equality. Two members sharing a
        # value would silently collapse into one branch and hide bugs.
        all_members = list(InstallStatus)
        values = {m.value for m in all_members}
        assert len(values) == len(all_members)


# ---------------------------------------------------------------------------
# InstallOutcome — typed return shape
# ---------------------------------------------------------------------------


class TestInstallOutcome:
    def test_should_carry_status_and_optional_message(self):
        from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus

        outcome = InstallOutcome(status=InstallStatus.SUCCESS, message="ok")

        assert outcome.status == InstallStatus.SUCCESS
        assert outcome.message == "ok"

    def test_message_should_default_to_empty_string(self):
        from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus

        outcome = InstallOutcome(status=InstallStatus.DECLINED)

        assert outcome.message == ""

    def test_should_be_immutable(self):
        # Why frozen: outcomes get logged, passed across layers, sometimes cached.
        # Mutation would mean a downstream caller silently rewriting history.
        from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus

        outcome = InstallOutcome(status=InstallStatus.SUCCESS)

        with pytest.raises((AttributeError, TypeError)):
            outcome.status = InstallStatus.FAILED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Installer protocol — structural typing check
# ---------------------------------------------------------------------------


class TestInstallerProtocol:
    def test_protocol_should_be_runtime_checkable(self):
        from lfx.services.local_model.installers.protocol import Installer

        # Why runtime_checkable: tests and the factory check `isinstance(x, Installer)`.
        # Without @runtime_checkable, isinstance() raises TypeError on protocols.
        class _Stub:
            def install(self, consent_callback):  # noqa: ARG002 — signature must match protocol
                from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus

                return InstallOutcome(status=InstallStatus.DECLINED)

        assert isinstance(_Stub(), Installer)

    def test_object_missing_install_should_not_satisfy_protocol(self):
        from lfx.services.local_model.installers.protocol import Installer

        class _NoInstall:
            pass

        assert not isinstance(_NoInstall(), Installer)
