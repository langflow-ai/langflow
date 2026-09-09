"""Command-line entry point used by release authentication workflows."""

from typing import TYPE_CHECKING

if __package__ or TYPE_CHECKING:
    from .release_auth.cli import main
else:
    from release_auth.cli import main

if __name__ == "__main__":
    main()
