"""Import extraction and categorization for custom component code."""

from __future__ import annotations

import ast
import re

from ..constants import KNOWN_INPUT_TYPES


def detect_input_types(code: str) -> set[str]:
    """Detect Input types used in custom component code."""
    found_types = set()
    for input_type in KNOWN_INPUT_TYPES:
        if re.search(rf"\b{input_type}\b", code):
            found_types.add(input_type)
    return found_types


def extract_imports_from_code(code: str) -> tuple[list[str], str]:
    """Extract import statements from custom component code using AST.

    Also removes `if TYPE_CHECKING:` blocks since they only contain type hints.
    Imports inside `try:` blocks are left in place to avoid empty try blocks.

    Returns:
        Tuple of (list of complete import statements, code without imports)
    """
    try:
        return _extract_imports_with_ast(code)
    except SyntaxError:
        return _extract_imports_simple(code)


def _extract_imports_with_ast(code: str) -> tuple[list[str], str]:
    """Extract imports using AST parsing."""
    imports: list[str] = []
    code_lines = code.split("\n")
    import_ranges: list[tuple[int, int]] = []
    type_checking_ranges: list[tuple[int, int]] = []
    try_block_ranges: list[tuple[int, int]] = []

    tree = ast.parse(code)

    # First pass: collect try block ranges
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            start_line = node.lineno - 1
            if node.handlers:
                end_line = node.handlers[0].lineno - 2
            else:
                end_line = (node.end_lineno - 1) if hasattr(node, "end_lineno") and node.end_lineno else start_line
            try_block_ranges.append((start_line, end_line))

    def is_inside_try_block(line_no: int) -> bool:
        return any(start < line_no <= end for start, end in try_block_ranges)

    # Second pass: collect imports and TYPE_CHECKING blocks
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start_line = node.lineno - 1
            end_line = (node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else node.lineno) - 1
            if not is_inside_try_block(start_line):
                import_ranges.append((start_line, end_line))
        elif isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                start_line = node.lineno - 1
                end_line = (node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else node.lineno) - 1
                type_checking_ranges.append((start_line, end_line))

    import_ranges.sort(key=lambda x: x[0])
    lines_to_remove: set[int] = set()

    for start, end in import_ranges:
        import_statement_lines = code_lines[start : end + 1]
        imports.append("\n".join(import_statement_lines))
        for line_no in range(start, end + 1):
            lines_to_remove.add(line_no)

    for start, end in type_checking_ranges:
        for line_no in range(start, end + 1):
            lines_to_remove.add(line_no)

    code_without_imports_lines = [line for i, line in enumerate(code_lines) if i not in lines_to_remove]
    while code_without_imports_lines and not code_without_imports_lines[0].strip():
        code_without_imports_lines.pop(0)

    return imports, "\n".join(code_without_imports_lines)


def _extract_imports_simple(code: str) -> tuple[list[str], str]:
    """Fallback: Extract imports using simple line matching."""
    lines = code.split("\n")
    imports: list[str] = []
    code_lines: list[str] = []
    in_imports = True

    for line in lines:
        stripped = line.strip()
        is_import_line = stripped.startswith(("import ", "from "))
        is_header_line = stripped == "" or stripped.startswith("#")

        if in_imports and (is_import_line or is_header_line):
            if is_import_line:
                imports.append(line)
        else:
            in_imports = False
            code_lines.append(line)

    while code_lines and not code_lines[0].strip():
        code_lines.pop(0)

    return imports, "\n".join(code_lines)


def categorize_imports(imports: list[str]) -> tuple[set[str], set[str], list[str]]:
    """Categorize imports into langflow, lfx, and other.

    Filters out `from __future__ import` since it's already at the top of the generated file.

    Returns:
        Tuple of (langflow_imports, lfx_imports, other_imports)
    """
    langflow_imports: set[str] = set()
    lfx_imports: set[str] = set()
    other_imports: list[str] = []

    for imp in imports:
        imp_stripped = imp.strip()
        if imp_stripped.startswith("from __future__"):
            continue
        if "langflow" in imp_stripped:
            langflow_imports.add(imp_stripped)
        elif imp_stripped.startswith(("from lfx", "import lfx")):
            lfx_imports.add(imp_stripped)
        elif imp_stripped:
            other_imports.append(imp_stripped)

    return langflow_imports, lfx_imports, other_imports


def strip_custom_code_imports(code: str) -> str:
    """Remove import statements from custom component code."""
    _, code_without_imports = extract_imports_from_code(code)
    return code_without_imports
