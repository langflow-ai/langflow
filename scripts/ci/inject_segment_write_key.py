import argparse
import ast
import os
from pathlib import Path
from zipfile import ZipFile

DEFAULT_DECLARATION = 'DEFAULT_SEGMENT_WRITE_KEY: Final = ""'
DEFAULT_TARGET = Path(__file__).resolve().parents[2] / "src/lfx/src/lfx/services/telemetry/constants.py"


def inject_segment_write_key(target: Path, write_key: str) -> None:
    if not write_key:
        msg = "LANGFLOW_SEGMENT_WRITE_KEY must be set for release builds"
        raise ValueError(msg)

    source = target.read_text()
    if source.count(DEFAULT_DECLARATION) != 1:
        msg = f"Expected one empty Segment write-key declaration in {target}"
        raise ValueError(msg)

    replacement = f"DEFAULT_SEGMENT_WRITE_KEY: Final = {write_key!r}  # pragma: allowlist secret"
    target.write_text(source.replace(DEFAULT_DECLARATION, replacement))


def verify_segment_write_key(wheel: Path, write_key: str) -> None:
    if not write_key:
        msg = "LANGFLOW_SEGMENT_WRITE_KEY must be set for release builds"
        raise ValueError(msg)

    with ZipFile(wheel) as archive:
        source = archive.read("lfx/services/telemetry/constants.py").decode()

    module = ast.parse(source)
    embedded_key = next(
        (
            node.value.value
            for node in module.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DEFAULT_SEGMENT_WRITE_KEY"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ),
        None,
    )
    if embedded_key != write_key:
        msg = f"{wheel} does not contain the expected Segment write key"
        raise ValueError(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-wheel", type=Path)
    args = parser.parse_args()
    key = os.environ.get("LANGFLOW_SEGMENT_WRITE_KEY", "")
    if args.verify_wheel:
        verify_segment_write_key(args.verify_wheel, key)
    else:
        inject_segment_write_key(DEFAULT_TARGET, key)
