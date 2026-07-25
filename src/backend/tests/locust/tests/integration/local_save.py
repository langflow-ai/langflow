"""Isolate SaveToFile Local writes outside the repo without process-global chdir."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def local_save_workdir(root: Path) -> Iterator[Path]:
    """Redirect SaveToFile Local writes under ``root/<uuid>`` via settings.

    When ``restrict_local_file_access`` is enabled, SaveToFile resolves bare
    ``file_name`` values under ``config_dir/<scope>/…``. Point ``config_dir`` at
    a unique temp directory (not process cwd) so concurrent tests cannot race
    on ``os.chdir``, then delete the directory on exit.
    """
    from lfx.services.deps import get_settings_service

    work = (root / f"perf-local-save-{uuid4().hex}").resolve()
    work.mkdir(parents=True, exist_ok=True)
    settings = get_settings_service().settings
    previous_restrict = settings.restrict_local_file_access
    previous_config_dir = settings.config_dir
    settings.restrict_local_file_access = True
    settings.config_dir = str(work)
    try:
        yield work
    finally:
        settings.restrict_local_file_access = previous_restrict
        settings.config_dir = previous_config_dir
        shutil.rmtree(work, ignore_errors=True)
