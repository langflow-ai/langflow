"""CLI to activate / deactivate auto-loading and to inspect registration.

The reliable, cross-platform way to run code at interpreter startup after a pip
install is a ``.pth`` file in the environment's ``site-packages`` whose single
line is ``import langflow_extra_providers``. Python's ``site`` module executes
that import on every interpreter start, which arms our lazy hook.

This file is written into the *active* environment's site-packages by the
``install`` command (run it once, in the same venv as Langflow). It survives
``pip install -U langflow`` because it lives alongside this package, not inside
Langflow's source tree.

Usage:
    python -m langflow_extra_providers install     # activate auto-load
    python -m langflow_extra_providers uninstall   # deactivate auto-load
    python -m langflow_extra_providers status      # show state + providers
    python -m langflow_extra_providers apply       # apply once in this process
"""

from __future__ import annotations

import argparse
import sysconfig
from pathlib import Path

_PTH_NAME = "langflow_extra_providers.pth"
_PTH_LINE = "import langflow_extra_providers\n"


def _pth_path() -> Path:
    return Path(sysconfig.get_path("purelib")) / _PTH_NAME


def cmd_install() -> int:
    path = _pth_path()
    try:
        path.write_text(_PTH_LINE, encoding="utf-8")
    except OSError as exc:
        print(f"Failed to write {path}: {exc}")
        print("You may need to run this inside the virtualenv where Langflow is installed.")
        return 1
    print(f"Activated auto-load: {path}")
    print("Restart the Langflow server to pick up the extra providers.")
    return 0


def cmd_uninstall() -> int:
    path = _pth_path()
    if path.exists():
        try:
            path.unlink()
        except OSError as exc:
            print(f"Failed to remove {path}: {exc}")
            return 1
        print(f"Deactivated auto-load: removed {path}")
    else:
        print(f"Auto-load was not active (no {path}).")
    return 0


def cmd_status() -> int:
    path = _pth_path()
    print(f"Auto-load .pth: {'present' if path.exists() else 'absent'} ({path})")
    from .config import load_provider_specs

    specs = load_provider_specs()
    print(f"Configured providers ({len(specs)}):")
    for name, spec in specs.items():
        models = ", ".join(m.get("name", "?") for m in spec.get("models", []))
        print(f"  - {name}: base_url={spec['base_url']} key={spec['api_key_var']}")
        if models:
            print(f"      models: {models}")
    return 0


def cmd_apply() -> int:
    from .patch import apply

    added = apply(force=True)
    if added:
        print(f"Registered providers in this process: {', '.join(added)}")
    else:
        print("No providers registered (is lfx / Langflow importable here?).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="langflow-extra-providers")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="Write the .pth file so providers auto-load at startup.")
    sub.add_parser("uninstall", help="Remove the .pth file.")
    sub.add_parser("status", help="Show auto-load state and configured providers.")
    sub.add_parser("apply", help="Register providers once in the current process.")
    args = parser.parse_args(argv)

    return {
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
        "apply": cmd_apply,
    }[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
