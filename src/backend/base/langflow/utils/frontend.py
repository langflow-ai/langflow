"""Prepare the portable frontend entrypoint for its public URL prefix."""

import re


def render_frontend_index(index_html: str, root_path: str) -> str:
    """Set the document base without modifying the installed frontend files."""
    prefix = root_path.strip().rstrip("/")
    if not re.fullmatch(r"(?:/[a-zA-Z0-9._~-]+)*", prefix) or any(part in {".", ".."} for part in prefix.split("/")):
        msg = "LANGFLOW_ROOT_PATH must be a URL path such as /langflow or /tools/langflow."
        raise ValueError(msg)

    # The prefix is restricted to URL path characters before entering HTML.
    return re.sub(r"<base\b[^>]*>", f'<base href="{prefix}/" />', index_html, count=1, flags=re.IGNORECASE)
