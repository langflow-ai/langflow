from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.ci.inject_segment_write_key import inject_segment_write_key, verify_segment_write_key


def test_inject_segment_write_key(tmp_path: Path) -> None:
    target = tmp_path / "constants.py"
    target.write_text('DEFAULT_SEGMENT_WRITE_KEY: Final = ""\n')

    inject_segment_write_key(target, "release'key")

    assert target.read_text() == 'DEFAULT_SEGMENT_WRITE_KEY: Final = "release\'key"  # pragma: allowlist secret\n'


def test_inject_segment_write_key_rejects_empty_key(tmp_path: Path) -> None:
    target = tmp_path / "constants.py"
    target.write_text('DEFAULT_SEGMENT_WRITE_KEY: Final = ""\n')

    with pytest.raises(ValueError, match="must be set"):
        inject_segment_write_key(target, "")


def test_verify_segment_write_key_in_wheel(tmp_path: Path) -> None:
    wheel = tmp_path / "lfx.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "lfx/services/telemetry/constants.py",
            "from typing import Final\nDEFAULT_SEGMENT_WRITE_KEY: Final = 'release-key'\n",
        )

    verify_segment_write_key(wheel, "release-key")

    with pytest.raises(ValueError, match="does not contain"):
        verify_segment_write_key(wheel, "wrong-key")
