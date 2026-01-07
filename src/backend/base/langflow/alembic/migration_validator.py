"""Migration Validator - Enforces Expand-Contract Pattern for Alembic migrations."""

import ast
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class MigrationPhase(Enum):
    EXPAND = "EXPAND"
    MIGRATE = "MIGRATE"
    CONTRACT = "CONTRACT"
    UNKNOWN = "UNKNOWN"


@dataclass
class Violation:
    type: str
    message: str
    line: int
    severity: str = "error"  # error or warning


class MigrationValidator:
    """Validates Alembic migrations follow Expand-Contract pattern."""

    VIOLATIONS = {
        "BREAKING_ADD_COLUMN": "Adding non-nullable column without default",
        "DIRECT_RENAME": "Direct column rename detected",
        "DIRECT_TYPE_CHANGE": "Direct type alteration detected",
        "IMMEDIATE_DROP": "Dropping column without migration phase",
        "MISSING_IDEMPOTENCY": "Migration not idempotent",
        "NO_PHASE_MARKER": "Migration missing phase documentation",
        "UNSAFE_ROLLBACK": "Downgrade may cause data loss",
        "MISSING_DOWNGRADE": "Downgrade function not implemented",
        "INVALID_PHASE_OPERATION": "Operation not allowed in this phase",
        "NO_EXISTENCE_CHECK": "Operation should check existence first",
        "MISSING_DATA_CHECK": "CONTRACT phase should verify data migration",
    }

    def __init__(self, *, strict_mode: bool = True):
        self.strict_mode = strict_mode

    ### Main validation method - it's a template method Go4 style.###

    def validate_migration_file(self, filepath: Path) -> dict[str, Any]:
        """Validate a single migration file."""
        if not filepath.exists():
            return {
                "file": str(filepath),
                "valid": False,
                "violations": [Violation("FILE_NOT_FOUND", f"File not found: {filepath}", 0)],
                "warnings": [],
            }

        content = filepath.read_text()

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {
                "file": str(filepath),
                "valid": False,
                "violations": [Violation("SYNTAX_ERROR", str(e), e.lineno or 0)],
                "warnings": [],
            }

        violations = []
        warnings = []

        # Check for phase documentation
        phase = self._extract_phase(content)
        if phase == MigrationPhase.UNKNOWN:
            violations.append(
                Violation("NO_PHASE_MARKER", "Migration must specify phase: EXPAND, MIGRATE, or CONTRACT", 1)
            )

        # Check upgrade function
        upgrade_node = self._find_function(tree, "upgrade")
        if upgrade_node:
            phase_violations = self._check_upgrade_operations(upgrade_node, phase)
            violations.extend(phase_violations)
        else:
            violations.append(Violation("MISSING_UPGRADE", "Migration must have an upgrade() function", 1))

        # Check downgrade function
        downgrade_node = self._find_function(tree, "downgrade")
        if downgrade_node:
            downgrade_issues = self._check_downgrade_safety(downgrade_node, phase)
            warnings.extend(downgrade_issues)
        elif phase != MigrationPhase.CONTRACT:  # CONTRACT phase may not support rollback
            violations.append(Violation("MISSING_DOWNGRADE", "Migration must have a downgrade() function", 1))

        # Additional phase-specific checks
        if phase == MigrationPhase.CONTRACT:
            contract_issues = self._check_contract_phase_requirements(content)
            violations.extend(contract_issues)

        return {
            "file": str(filepath),
            "valid": len(violations) == 0,
            "violations": [v.__dict__ for v in violations],
            "warnings": [w.__dict__ for w in warnings],
            "phase": phase.value,
        }

    # Method to check DB operations constraints imposed by phases -
    # New constraint requirements should be added here

    def _check_upgrade_operations(self, node: ast.FunctionDef, phase: MigrationPhase) -> list[Violation]:
        """Check upgrade operations for violations."""
        violations = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if self._is_op_call(child, "add_column"):
                    violations.extend(self._check_add_column(child, phase, node))

                elif self._is_op_call(child, "alter_column"):
                    violations.extend(self._check_alter_column(child, phase))

                elif self._is_op_call(child, "drop_column"):
                    violations.extend(self._check_drop_column(child, phase))

                elif self._is_op_call(child, "rename_table") or self._is_op_call(child, "rename_column"):
                    violations.append(
                        Violation("DIRECT_RENAME", "Use expand-contract pattern instead of direct rename", child.lineno)
                    )

        return violations

    def _check_add_column(self, call: ast.Call, phase: MigrationPhase, func_node: ast.FunctionDef) -> list[Violation]:
        """Check add_column operations."""
        violations = []

        # Check if column is nullable or has default
        if not self._has_nullable_true(call) and not self._has_server_default(call):
            violations.append(
                Violation(
                    "BREAKING_ADD_COLUMN", "New columns must be nullable=True or have server_default", call.lineno
                )
            )

        # Check for idempotency
        if not self._has_existence_check_nearby(func_node, call):
            violations.append(
                Violation(
                    "NO_EXISTENCE_CHECK", "add_column should check if column exists first (idempotency)", call.lineno
                )
            )

        # Phase-specific checks
        if phase == MigrationPhase.CONTRACT:
            violations.append(Violation("INVALID_PHASE_OPERATION", "Cannot add columns in CONTRACT phase", call.lineno))

        return violations

    def _check_alter_column(self, call: ast.Call, phase: MigrationPhase) -> list[Violation]:
        """Check alter_column operations."""
        violations = []

        # Check for type changes
        if self._has_type_change(call) and phase != MigrationPhase.CONTRACT:
            violations.append(
                Violation("DIRECT_TYPE_CHANGE", "Type changes should use expand-contract pattern", call.lineno)
            )

        # Check for nullable changes
        if self._changes_nullable_to_false(call) and phase != MigrationPhase.CONTRACT:
            violations.append(
                Violation(
                    "BREAKING_ADD_COLUMN", "Making column non-nullable only allowed in CONTRACT phase", call.lineno
                )
            )

        return violations

    def _check_drop_column(self, call: ast.Call, phase: MigrationPhase) -> list[Violation]:
        """Check drop_column operations."""
        violations = []

        if phase != MigrationPhase.CONTRACT:
            violations.append(
                Violation(
                    "IMMEDIATE_DROP",
                    f"Column drops only allowed in CONTRACT phase (current: {phase.value})",
                    call.lineno,
                )
            )

        return violations

    def _check_contract_phase_requirements(self, content: str) -> list[Violation]:
        """Check CONTRACT phase specific requirements."""
        # Check for data migration before dropping columns
        if not ("SELECT" in content and "COUNT" in content):
            return [
                Violation(
                    "MISSING_DATA_CHECK",
                    "CONTRACT phase should verify data migration before dropping columns",
                    1,
                    severity="warning",
                )
            ]
        return []

    def _check_downgrade_safety(self, node: ast.FunctionDef, phase: MigrationPhase) -> list[Violation]:
        """Check downgrade function for safety issues."""
        warnings = []

        # Check if downgrade might lose data
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and self._is_op_call(child, "alter_column"):
                # Check if there's a backup mechanism
                func_content = ast.unparse(node)
                if "backup" not in func_content.lower() and "SELECT" not in func_content:
                    warnings.append(
                        Violation(
                            "UNSAFE_ROLLBACK",
                            "Downgrade drops column without checking/backing up data",
                            child.lineno,
                            severity="warning",
                        )
                    )

        # CONTRACT phase special handling
        if phase == MigrationPhase.CONTRACT:
            func_content = ast.unparse(node)
            if "NotImplementedError" not in func_content and "raise" not in func_content:
                warnings.append(
                    Violation(
                        "UNSAFE_ROLLBACK",
                        "CONTRACT phase downgrade should raise NotImplementedError or handle carefully",
                        node.lineno,
                        severity="warning",
                    )
                )

        return warnings

    def _is_op_call(self, call: ast.Call, method: str) -> bool:
        """Check if call is op.method()."""
        func = call.func

        # Avoid multiple attribute resolutions and isinstance checks
        if type(func) is ast.Attribute:
            val = func.value
            if type(val) is ast.Name:
                return val.id == "op" and func.attr == method
        return False

    def _has_nullable_true(self, call: ast.Call) -> bool:
        """Check if call has nullable=True."""
        for keyword in call.keywords:
            if keyword.arg == "nullable" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value is True

        for call_arg in call.args:
            if isinstance(call_arg, ast.Call):
                return self._has_nullable_true(call_arg)

        return False

    def _has_server_default(self, call: ast.Call) -> bool:
        """Check if call has server_default."""
        return any(kw.arg == "server_default" for kw in call.keywords)

    def _has_type_change(self, call: ast.Call) -> bool:
        """Check if alter_column changes type."""
        return any(kw.arg in ["type_", "type"] for kw in call.keywords)

    def _changes_nullable_to_false(self, call: ast.Call) -> bool:
        """Check if alter_column sets nullable=False."""
        for keyword in call.keywords:
            if keyword.arg == "nullable" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value is False
        return False

    ### Helper method to check for existence checks around operations.
    # It looks for if statements that might be checking column existence
    # TODO: Evaluate if more sophisticated analysis is needed for existence checks
    def _has_existence_check_nearby(self, func_node: ast.FunctionDef, target_call: ast.Call) -> bool:
        """Check if operation is wrapped in existence check."""
        # Look for if statements that might be checking column existence
        for node in ast.walk(func_node):
            if isinstance(node, ast.If):
                # Check if this if statement contains our target call
                for child in ast.walk(node):
                    if child == target_call:
                        # Check if the condition mentions columns or inspector
                        condition = ast.unparse(node.test)
                        if any(keyword in condition.lower() for keyword in ["column", "inspector", "not in", "if not"]):
                            return True
        return False

    ### Helper methods ###

    def _extract_phase(self, content: str) -> MigrationPhase:
        """Extract migration phase from documentation."""
        # TODO: Support phase detection from inline comments and function
        # annotations, not just docstrings or top-level comments.
        # Look in docstring or comments
        phase_pattern = r"Phase:\s*(EXPAND|MIGRATE|CONTRACT)"
        match = re.search(phase_pattern, content, re.IGNORECASE)

        if match:
            phase_str = match.group(1).upper()
            return MigrationPhase[phase_str]

        return MigrationPhase.UNKNOWN

    def _find_function(self, tree: ast.Module, name: str) -> ast.FunctionDef | None:
        """Find a function by name in the AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Alembic migrations")
    parser.add_argument("files", nargs="+", help="Migration files to validate")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")

    args = parser.parse_args()

    validator = MigrationValidator(strict_mode=args.strict)
    all_valid = True
    results = []

    for file_path in args.files:
        result = validator.validate_migration_file(Path(file_path))
        results.append(result)

        if not result["valid"]:
            all_valid = False

        if args.strict and result["warnings"]:
            all_valid = False

    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("migration_validator")
    if args.json:
        logger.info(json.dumps(results, indent=2))
    else:
        for result in results:
            logger.info("\n%s", "=" * 60)
            logger.info("File: %s", result["file"])
            logger.info("Phase: %s", result["phase"])
            logger.info("Valid: %s", "✅" if result["valid"] else "❌")

            if result["violations"]:
                logger.error("\n❌ Violations:")
                for v in result["violations"]:
                    logger.error("  Line %s: %s - %s", v["line"], v["type"], v["message"])

            if result["warnings"]:
                logger.warning("\n⚠️  Warnings:")
                for w in result["warnings"]:
                    logger.warning("  Line %s: %s - %s", w["line"], w["type"], w["message"])

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
