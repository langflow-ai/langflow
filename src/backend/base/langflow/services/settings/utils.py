import platform
from pathlib import Path

from loguru import logger


def set_secure_permissions(file_path: Path) -> None:
    if platform.system() in {"Linux", "Darwin"}:  # Unix/Linux/Mac
        file_path.chmod(0o600)
    elif platform.system() == "Windows":
        import win32api
        import win32con
        import win32security

        user, _, _ = win32security.LookupAccountName("", win32api.GetUserName())
        sd = win32security.GetFileSecurity(str(file_path), win32security.DACL_SECURITY_INFORMATION)
        dacl = win32security.ACL()

        # Set the new DACL for the file: read and write access for the owner, no access for everyone else
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            user,
        )
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(str(file_path), win32security.DACL_SECURITY_INFORMATION, sd)
    else:
        logger.error("Unsupported OS")


def write_secret_to_file(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    try:
        set_secure_permissions(path)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to set secure permissions on secret key")


def read_secret_from_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")
