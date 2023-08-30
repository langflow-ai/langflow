import os
import platform


def set_secure_permissions(file_path):
    if platform.system() in ["Linux", "Darwin"]:  # Unix/Linux/Mac
        os.chmod(file_path, 0o600)
    elif platform.system() == "Windows":
        import win32api
        import win32con
        import win32security

        user, domain, _ = win32security.LookupAccountName("", win32api.GetUserName())
        sd = win32security.GetFileSecurity(
            file_path, win32security.DACL_SECURITY_INFORMATION
        )
        dacl = win32security.ACL()

        # Set the new DACL for the file: read and write access for the owner, no access for everyone else
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            user,
        )
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(
            file_path, win32security.DACL_SECURITY_INFORMATION, sd
        )
    else:
        print("Unsupported OS")
