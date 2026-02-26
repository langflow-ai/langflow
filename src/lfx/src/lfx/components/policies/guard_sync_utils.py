"""Utility functions for synchronizing generated guard code with component inputs."""

from pathlib import Path

from toolguard.runtime.runtime import RESULTS_FILENAME

from lfx.io import CodeInput
from lfx.log.logger import logger

GENERATED_GUARD_INFO_PREFIX = "Auto-generated ToolGuard code for "


def is_generated_guard_field(field: dict) -> bool:
    """Check if a field represents a generated guard code input.

    Args:
        field: Dictionary representing a component field/input

    Returns:
        True if the field is a generated guard code field, False otherwise
    """
    if not isinstance(field, dict):
        return False
    return (
        field.get("type") == "code"
        and field.get("dynamic") is True
        and isinstance(field.get("info"), str)
        and field.get("info", "").startswith(GENERATED_GUARD_INFO_PREFIX)
    )


def sync_generated_guard_code_inputs(
    build_config: dict,
    work_dir: Path,
    step2_subdir: str,
    project_name: str,
) -> dict:
    """Synchronize generated guard code files with component code inputs.

    Scans the generated guard code directory and creates/updates CodeInput fields
    in the build config for each Python file found. Removes stale fields for files
    that no longer exist.

    Args:
        build_config: The component's build configuration dictionary
        work_dir: Base working directory for the toolguard project
        step2_subdir: Subdirectory name containing generated code (e.g., "Step_2")
        project_name: Name of the project in snake_case format

    Returns:
        Updated build_config dictionary with synchronized code inputs
    """
    logger.info("Syncing files...")
    generated_field_names = {key for key, value in build_config.items() if is_generated_guard_field(value)}

    step2_dir = work_dir / step2_subdir
    logger.info(f"step2_dir = {step2_dir}")
    logger.info(f"step2_dir.exists() = {step2_dir.exists()}")
    logger.info(f"step2_dir.is_dir() = {step2_dir.is_dir()}")
    if not step2_dir.exists() or not step2_dir.is_dir():
        for field_name in generated_field_names:
            build_config.pop(field_name, None)
        return build_config

    files = sorted(path for path in step2_dir.rglob("*") if path.is_file())

    def include_file(relative_name) -> bool:
        if relative_name.startswith(project_name) and relative_name.endswith(".py"):
            return True
        return relative_name == str(RESULTS_FILENAME)

    next_generated_names: set[str] = set()

    for file_path in files:
        relative_name = file_path.relative_to(step2_dir).as_posix()
        if not include_file(relative_name):
            continue
        logger.info("---" + relative_name)
        next_generated_names.add(relative_name)
        try:
            code_value = file_path.read_text(encoding="utf-8")
        except OSError:
            code_value = ""

        code_input = CodeInput(
            name=relative_name,
            display_name=relative_name,
            value=code_value,
            info=f"{GENERATED_GUARD_INFO_PREFIX}{relative_name}",
            dynamic=True,
            advanced=True,
        )
        build_config[relative_name] = code_input.to_dict()

    stale_field_names = generated_field_names - next_generated_names
    for field_name in stale_field_names:
        build_config.pop(field_name, None)

    return build_config
