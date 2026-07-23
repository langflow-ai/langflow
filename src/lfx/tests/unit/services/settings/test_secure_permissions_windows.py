"""Windows DACL hardening for the secret_key file.

Regression tests for the machine-name/username collision bug: when the
computer name equals the username (e.g. computer DANIEL, user daniel),
``LookupAccountName("", GetUserName())`` resolves the bare name to the
machine-domain object (SidTypeDomain, no user RID). Writing a DACL that
grants access only to that SID locks out the real user, and the next
startup dies with PermissionError when reading the secret_key back.

The fix takes the user SID from the process token instead of resolving
by name, and read_secret_from_file self-heals files whose DACL was
already broken by an affected version.
"""

import platform
from pathlib import Path

import pytest
from lfx.services.settings.utils import (
    read_secret_from_file,
    set_secure_permissions,
    write_secret_to_file,
)

pytestmark = pytest.mark.skipif(platform.system() != "Windows", reason="Windows DACL behavior")

SECRET = "test-secret-value"  # noqa: S105


def _current_process_user_sid():
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    sid, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
    return sid


def _dacl_sids(path: Path) -> list:
    import win32security

    sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
    dacl = sd.GetSecurityDescriptorDacl()
    assert dacl is not None, "expected a protected DACL, got NULL (allow-everyone)"
    return [dacl.GetAce(i)[2] for i in range(dacl.GetAceCount())]


def _apply_broken_domain_sid_dacl(path: Path) -> None:
    """Reproduce the DACL an affected version wrote: single ACE for the machine-domain SID."""
    import win32api
    import win32con
    import win32security

    domain_sid, _, sid_type = win32security.LookupAccountName("", win32api.GetComputerName())
    assert sid_type == win32security.SidTypeDomain
    sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        win32con.GENERIC_READ | win32con.GENERIC_WRITE,
        domain_sid,
    )
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION, sd)


@pytest.fixture
def secret_path(tmp_path: Path):
    path = tmp_path / "secret_key"
    yield path
    # Reset the ACL so pytest can clean tmp_path even after a broken-DACL test.
    if path.exists():
        import win32security

        sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
        sd.SetSecurityDescriptorDacl(1, None, 0)
        win32security.SetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION, sd)


def test_write_then_read_roundtrip(secret_path: Path):
    write_secret_to_file(secret_path, SECRET)
    assert read_secret_from_file(secret_path) == SECRET


def test_dacl_grants_the_process_token_user(secret_path: Path):
    """The ACE must target the token user SID, never a name-resolved principal."""
    write_secret_to_file(secret_path, SECRET)
    sids = _dacl_sids(secret_path)
    assert sids == [_current_process_user_sid()]


def test_survives_machine_name_username_collision(secret_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Simulate computer name == username: GetUserName() returns the machine name.

    On an affected host the bare name resolves to the machine-domain SID; a fix
    based on the process token must be immune to whatever GetUserName returns.
    """
    import win32api

    monkeypatch.setattr(win32api, "GetUserName", win32api.GetComputerName)
    write_secret_to_file(secret_path, SECRET)
    assert read_secret_from_file(secret_path) == SECRET
    sids = _dacl_sids(secret_path)
    assert sids == [_current_process_user_sid()]


def test_read_self_heals_broken_dacl(secret_path: Path):
    """Installs already hit by the bug must recover without manual icacls /reset."""
    secret_path.write_text(SECRET, encoding="utf-8")
    _apply_broken_domain_sid_dacl(secret_path)
    with pytest.raises(PermissionError):
        secret_path.read_text(encoding="utf-8")

    assert read_secret_from_file(secret_path) == SECRET
    # The repaired file must stay readable and carry the correct ACE.
    assert secret_path.read_text(encoding="utf-8") == SECRET
    assert _dacl_sids(secret_path) == [_current_process_user_sid()]


def test_set_secure_permissions_direct(secret_path: Path):
    secret_path.write_text(SECRET, encoding="utf-8")
    set_secure_permissions(secret_path)
    assert secret_path.read_text(encoding="utf-8") == SECRET
