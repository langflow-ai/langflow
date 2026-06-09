import platform
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from lfx.log.logger import logger


class RSAKeyError(Exception):
    """Exception raised when RSA key operations fail."""


def derive_public_key_from_private(private_key_pem: str) -> str:
    """Derive a public key from a private key PEM string.

    Args:
        private_key_pem: The private key in PEM format.

    Returns:
        str: The public key in PEM format.

    Raises:
        RSAKeyError: If the private key is invalid or cannot be processed.
    """
    try:
        private_key = load_pem_private_key(private_key_pem.encode(), password=None)
        return (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
    except Exception as e:
        msg = f"Failed to derive public key from private key: {e}"
        logger.error(msg)
        raise RSAKeyError(msg) from e


def generate_rsa_key_pair() -> tuple[str, str]:
    """Generate an RSA key pair for RS256 JWT signing.

    Returns:
        tuple[str, str]: A tuple of (private_key_pem, public_key_pem) as strings.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    return private_key_pem, public_key_pem


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


def write_public_key_to_file(path: Path, value: str) -> None:
    """Write a public key to file with appropriate permissions (0o644).

    Public keys can be readable by others but should only be writable by owner.

    Args:
        path: The file path to write to.
        value: The public key content.
    """
    path.write_text(value, encoding="utf-8")
    try:
        if platform.system() in {"Linux", "Darwin"}:
            path.chmod(0o644)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to set permissions on public key file")
