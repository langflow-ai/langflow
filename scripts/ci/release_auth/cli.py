"""Disable auto-login in official artifacts while preserving local build defaults."""

from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import AUTH_SOURCE
from .preparation import prepare_release_auth
from .tags import prepare_release_tag
from .validation import verify_release_source, verify_release_wheel

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    """Dispatch release authentication commands with actionable failure messages."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Set the release checkout's AUTO_LOGIN default to False")
    prepare.add_argument("source", type=Path, nargs="?", default=AUTH_SOURCE)
    verify = commands.add_parser("verify", help="Verify built LFX release wheels before publication")
    verify.add_argument("wheels", type=Path, nargs="+")
    verify_source = commands.add_parser("verify-source", help="Verify the checked-out release source")
    verify_source.add_argument("source", type=Path, nargs="?", default=AUTH_SOURCE)
    tag = commands.add_parser("tag", help="Create an unpublished release-only source tag without moving a branch")
    tag.add_argument("tag")
    tag.add_argument("--ref", default="HEAD")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare_release_auth(args.source)
            print(f"Prepared {args.source} with AUTO_LOGIN=False")
        elif args.command == "verify":
            for wheel in args.wheels:
                verify_release_wheel(wheel)
                print(f"Verified {wheel.name}: AUTO_LOGIN=False")
        elif args.command == "verify-source":
            verify_release_source(args.source)
            print(f"Verified {args.source}: AUTO_LOGIN=False")
        else:
            print(prepare_release_tag(Path.cwd(), args.tag, args.ref))
    except subprocess.CalledProcessError as exc:
        parser.error(f"Git operation failed: {exc.stderr.decode().strip()}")
    except (OSError, SyntaxError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
