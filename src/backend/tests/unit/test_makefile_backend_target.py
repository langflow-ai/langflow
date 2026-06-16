"""Ensure the Makefile backend target scopes --reload to source directories only.

Without --reload-dir, uvicorn watches everything including .venv, causing
constant reloads from package files and making the dev server unusable.
"""

from pathlib import Path


def test_backend_reload_scoped_to_source_dirs():
    makefile = (Path(__file__).parents[4] / "Makefile").read_text()

    # Both login and non-login variants must scope reload
    assert "--reload-dir src/backend" in makefile, (
        "Makefile backend target must include --reload-dir src/backend "
        "to prevent uvicorn from watching .venv"
    )
    assert "--reload-dir src/lfx" in makefile, (
        "Makefile backend target must include --reload-dir src/lfx"
    )

    # Bare --reload without a reload-dir would still watch everything
    lines_with_bare_reload = [
        line for line in makefile.splitlines()
        if "--reload" in line and "--reload-dir" not in line and line.strip().startswith("$(if")
    ]
    assert not lines_with_bare_reload, (
        f"Found bare --reload without --reload-dir: {lines_with_bare_reload}"
    )
