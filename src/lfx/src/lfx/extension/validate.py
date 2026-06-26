"""Offline, non-executing validator for a Langflow Extension.

``validate_extension`` is the function backing the ``lfx extension validate``
CLI.  It performs four passes:

    1. **Manifest discovery + schema validation**
       (:func:`~lfx.extension.manifest.load_manifest`).
    2. **Path-safety**: bundle paths must resolve inside the extension root,
       no ``..``, no absolute paths, no symlinks that escape the bundle dir.
    3. **AST-level hygiene lint** of every ``*.py`` file in the bundle:
       syntax check, presence of at least one ``Component`` subclass with a
       declared ``build`` method, rejection of top-level wildcard imports,
       flag of top-level dynamic-evaluation primitives (``open``, ``socket``,
       ``subprocess``, ``os.system``, ``exec``, ``eval``, ``__import__``,
       ``compile``).  **This is best-effort lint, not a security sandbox**:
       it only catches literal name patterns and is trivially bypassable by
       obfuscation (``getattr``, base64, aliasing).  Operators must still
       treat third-party bundles as untrusted code.
    4. **(opt-in)** ``--execute-imports``: forks a subprocess with a temporary
       Langflow state dir, a strict env allowlist, and no inherited server
       state, imports each bundle module, and reports failures.  Still
       executes arbitrary Python; see the CLI help for the trust caveat.

The validator NEVER imports the bundle's own code in-process; that's what
``--execute-imports`` is for, and the ticket is explicit that even then it
must run out-of-process.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from lfx.extension._paths import is_within
from lfx.extension.errors import (
    ExtensionError,
    ExtensionErrorCollection,
)
from lfx.extension.manifest import (
    DEFERRED_FIELDS,
    ExtensionManifest,
    ManifestSource,
    _read_extension_json,
    _read_pyproject_extension,
)

# ---------------------------------------------------------------------------
# AST inspection sentinels
# ---------------------------------------------------------------------------

# Names of top-level I/O / dynamic-evaluation primitives that, when called
# at module import time, are considered side effects.  This list is a
# best-effort hygiene lint, not a security boundary: an attacker who wants
# to evade detection can trivially do so (``getattr(os, "sys"+"tem")``,
# base64, aliased imports).  False positives here are easy to silence
# (move the call into a function); false negatives are an accepted limitation
# of static literal-name matching.
_IO_NAMES: frozenset[str] = frozenset(
    {
        "open",
        "socket",
        "subprocess",
        # Dynamic-evaluation primitives. A bundle that calls these at module
        # top level either has a real bug or is doing something the reviewer
        # should see; flagging them is consistent with the "import-safe
        # modules only" contract documented in BUNDLE_API.md.
        "exec",
        "eval",
        "compile",
        "__import__",
    }
)

# ``os.system``-style attribute calls handled separately so we can preserve
# the dotted location string in the error.
_IO_DOTTED_NAMES: frozenset[tuple[str, str]] = frozenset(
    {
        ("os", "system"),
        ("os", "popen"),
        ("os", "execv"),
        ("os", "execvp"),
        ("os", "execve"),
        ("subprocess", "run"),
        ("subprocess", "Popen"),
        ("subprocess", "call"),
        ("subprocess", "check_call"),
        ("subprocess", "check_output"),
        ("socket", "socket"),
        ("socket", "create_connection"),
        # Dynamic-import attribute calls. ``importlib.import_module(...)``
        # at module top level is a common obfuscation vector that the simple
        # ``__import__`` name match misses.
        ("importlib", "import_module"),
        ("importlib", "__import__"),
    }
)


# ---------------------------------------------------------------------------
# ValidateReport
# ---------------------------------------------------------------------------


@dataclass
class ValidateReport:
    """Outcome of a validate run.

    ``manifest`` is set when discovery and schema validation succeeded, even
    if downstream passes (paths, AST) found errors.  ``ok`` is the single bit
    callers should branch on; the CLI maps it to the process exit code.
    """

    root: Path
    errors: ExtensionErrorCollection = field(default_factory=ExtensionErrorCollection)
    manifest: ExtensionManifest | None = None
    manifest_source: ManifestSource | None = None
    bundle_files_scanned: int = 0

    @property
    def ok(self) -> bool:
        return self.errors.ok


# ---------------------------------------------------------------------------
# Pass 1: manifest discovery + schema validation
# ---------------------------------------------------------------------------


def _format_pydantic_error(exc: ValidationError) -> tuple[str, list[str]]:
    """Render a Pydantic ValidationError into (summary, [unused-here]).

    The second tuple element is preserved for symmetry with previous tickets'
    error contracts; deferred-field detection happens earlier (pre-validate)
    in ``_validate_manifest_phase`` so it does not depend on Pydantic's
    error-code stability.
    """
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "validation error")
        parts.append(f"{loc or '<root>'}: {msg}")
    summary = "; ".join(parts) if parts else "manifest fails schema validation"
    return summary, []


def _discover_manifest_data(
    root: Path,
) -> tuple[Path | None, str | None, dict | None, ExtensionError | None]:
    """Locate and parse the raw manifest data without invoking model validation.

    Returns ``(source_path, kind, raw_data, error)``; if ``error`` is non-None,
    the rest are best-effort (``source_path`` may still be set so the caller
    can attribute the failure to a specific file).
    """
    extension_json = root / "extension.json"
    pyproject = root / "pyproject.toml"

    if extension_json.is_file():
        try:
            return (
                extension_json,
                "extension.json",
                _read_extension_json(extension_json),
                None,
            )
        except (ValueError, TypeError) as exc:
            return (
                extension_json,
                "extension.json",
                None,
                ExtensionError(
                    code="manifest-invalid",
                    message=str(exc),
                    location=str(extension_json),
                    hint="Fix the manifest so it parses as JSON.",
                ),
            )
        except OSError as exc:
            return (
                extension_json,
                "extension.json",
                None,
                ExtensionError(
                    code="manifest-unreadable",
                    message=str(exc),
                    location=str(extension_json),
                    hint="Check file permissions and re-run.",
                ),
            )

    if pyproject.is_file():
        try:
            section = _read_pyproject_extension(pyproject)
        except (ValueError, TypeError) as exc:
            return (
                pyproject,
                "pyproject.toml",
                None,
                ExtensionError(
                    code="manifest-invalid",
                    message=str(exc),
                    location=str(pyproject),
                    hint="Fix the pyproject.toml so it parses as TOML.",
                ),
            )
        except OSError as exc:
            return (
                pyproject,
                "pyproject.toml",
                None,
                ExtensionError(
                    code="manifest-unreadable",
                    message=str(exc),
                    location=str(pyproject),
                    hint="Check file permissions and re-run.",
                ),
            )
        if section is not None:
            return pyproject, "pyproject.toml", section, None

    return (
        None,
        None,
        None,
        ExtensionError(
            code="manifest-not-found",
            message=(f"No extension.json or [tool.langflow.extension] entry found in {root}."),
            location=str(root),
            hint=(
                "Create an extension.json at the extension root or add a "
                "[tool.langflow.extension] section to pyproject.toml. See "
                "the manifest reference for the minimal shape."
            ),
        ),
    )


def _validate_manifest_phase(root: Path, report: ValidateReport) -> ManifestSource | None:
    """Run pass 1: discovery + schema.  Updates ``report`` and returns a source."""
    source_path, kind, raw_data, error = _discover_manifest_data(root)
    if error is not None:
        report.errors.add_error(error)
        return None
    # _discover_manifest_data's contract: success implies all three present.
    if source_path is None or kind is None or raw_data is None:  # pragma: no cover
        msg = "manifest discovery returned an inconsistent result"
        raise RuntimeError(msg)

    # Detect multi-bundle BEFORE model_validate so the dedicated discriminant
    # fires reliably even if other manifest fields are also wrong.
    bundles = raw_data.get("bundles") if isinstance(raw_data, dict) else None
    if isinstance(bundles, list) and len(bundles) > 1:
        report.errors.add_error(
            ExtensionError(
                code="multi-bundle-unsupported",
                message=(
                    f"Manifest declares {len(bundles)} bundles; v0 accepts exactly one. "
                    "Multi-bundle support is deferred to a future milestone."
                ),
                location=f"{source_path}:bundles",
                hint=("Split each bundle into its own Extension distribution until multi-bundle support ships."),
            )
        )
        return None

    # Detect deferred fields BEFORE model_validate so that authors get a clean
    # discriminant rather than a generic schema error wall.
    deferred_present: list[str] = []
    if isinstance(raw_data, dict):
        deferred_present.extend(
            field_name for field_name in DEFERRED_FIELDS if field_name in raw_data and raw_data[field_name] is not None
        )
    if deferred_present:
        for field_name in deferred_present:
            report.errors.add_error(
                ExtensionError(
                    code="field-deferred-in-this-milestone",
                    message=(
                        f"Manifest field {field_name!r} is reserved for a future milestone; v0 rejects non-null values."
                    ),
                    location=f"{source_path}:{field_name}",
                    content=field_name,
                    hint=(
                        f"Remove the {field_name!r} field from the manifest. "
                        "It will be re-enabled in a later milestone."
                    ),
                )
            )
        return None

    try:
        manifest = ExtensionManifest.model_validate(raw_data)
    except ValidationError as exc:
        summary, _ = _format_pydantic_error(exc)
        report.errors.add_error(
            ExtensionError(
                code="manifest-invalid",
                message=summary,
                location=str(source_path),
                hint="Fix the manifest so it conforms to the v1 schema.",
            )
        )
        return None

    source = ManifestSource(manifest=manifest, path=source_path, kind=kind)
    report.manifest = manifest
    report.manifest_source = source
    return source


# ---------------------------------------------------------------------------
# Pass 2: path-safety
# ---------------------------------------------------------------------------


def _resolve_bundle_path(root: Path, bundle_path: str) -> tuple[Path | None, ExtensionError | None]:
    """Resolve a bundle path under ``root`` while enforcing safety rules.

    Returns a (resolved_path, error) tuple; exactly one is populated.
    """
    candidate = root / bundle_path
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, ExtensionError(
            code="path-escape",
            message=f"Could not resolve bundle path: {exc}",
            location=bundle_path,
            content=bundle_path,
            hint="Make sure the bundle path resolves to a directory under the manifest.",
        )

    if not is_within(resolved, root):
        root_resolved = root.resolve(strict=False)
        return None, ExtensionError(
            code="path-escape",
            message=(
                f"Bundle path {bundle_path!r} resolves to {resolved}, which is "
                f"outside the extension root {root_resolved}."
            ),
            location=bundle_path,
            content=bundle_path,
            hint="Move the bundle directory inside the extension root.",
        )

    if not resolved.exists():
        return None, ExtensionError(
            code="bundle-path-not-found",
            message=f"Bundle path {bundle_path!r} does not exist.",
            location="bundles[].path",
            content=bundle_path,
            hint="Create the bundle directory or fix the manifest path.",
        )
    if not resolved.is_dir():
        return None, ExtensionError(
            code="bundle-path-not-found",
            message=f"Bundle path {bundle_path!r} is not a directory.",
            location="bundles[].path",
            content=bundle_path,
            hint="Point bundles[].path at a directory, not a file.",
        )
    return resolved, None


# ---------------------------------------------------------------------------
# Pass 3: AST inspection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BundleAstSummary:
    """Per-bundle AST findings.

    Used to make per-bundle decisions that need the *aggregate* result
    (e.g. "no Component subclass anywhere").
    """

    bundle_name: str
    bundle_root: Path
    has_component_subclass: bool


def _is_component_class(node: ast.ClassDef) -> bool:
    """Heuristic for "this class looks like a Component subclass".

    A class is treated as a Component if any base name is ``Component`` or
    ends with ``Component`` (so ``LCComponent``, ``BaseComponent``, ... all
    match).  Static analysis cannot resolve the actual MRO, so we err on the
    side of accepting plausible candidates and let the loader do the real
    isinstance check at registration time.
    """
    for base in node.bases:
        if isinstance(base, ast.Name) and (base.id == "Component" or base.id.endswith("Component")):
            return True
        if isinstance(base, ast.Attribute) and (base.attr == "Component" or base.attr.endswith("Component")):
            return True
    return False


def _has_build_method(node: ast.ClassDef) -> bool:
    """Return True if the class body declares an invocable entry-point.

    Langflow Components reach the runtime in two shapes:

    1. A literal ``build`` method on the class (the original convention).
    2. A method named in an ``Output(method="...")`` declaration in the
       class-level ``outputs = [...]`` assignment.  This is the more
       common modern shape: a component can declare multiple outputs that
       each call a different method.  Neither DuckDuckGo nor arXiv ships a
       literal ``build``; both are valid.

    The validator accepts either form.  If a class declares
    ``Output(method="X")`` but no ``def X(...)`` in the class body,
    that's still flagged -- it would crash at run-time anyway.
    """
    method_names = {item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if "build" in method_names:
        return True
    return any(invocable in method_names for invocable in _output_method_names(node))


def _output_method_names(node: ast.ClassDef) -> set[str]:
    """Collect method names referenced by ``Output(method="...")`` calls in the class body.

    Walks the class-level assignment ``outputs = [...]`` and pulls the
    string value of every ``method=`` keyword argument on a call whose
    callee is the name ``Output`` (or anything ending in ``Output``).
    Static analysis only -- if the list is built dynamically, we miss
    those names and the literal-``build`` fallback still applies.
    """
    names: set[str] = set()
    for item in node.body:
        if isinstance(item, ast.Assign):
            targets = item.targets
            value = item.value
        elif isinstance(item, ast.AnnAssign):
            if item.value is None:
                continue
            targets = [item.target]
            value = item.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "outputs" for t in targets):
            continue
        for sub in ast.walk(value):
            if not isinstance(sub, ast.Call):
                continue
            callee = sub.func
            if isinstance(callee, ast.Name):
                callee_name = callee.id
            elif isinstance(callee, ast.Attribute):
                callee_name = callee.attr
            else:
                continue
            if callee_name != "Output" and not callee_name.endswith("Output"):
                continue
            for kw in sub.keywords:
                if kw.arg != "method":
                    continue
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    names.add(kw.value.value)
    return names


def _find_top_level_io(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, symbol)`` for top-level call expressions that touch I/O.

    Only inspects module-level Expr / Assign statements; calls inside function
    or class bodies are out of scope (they don't run at import time).
    """
    findings: list[tuple[int, str]] = []
    if not isinstance(tree, ast.Module):
        return findings
    for stmt in tree.body:
        # We descend into `with`, `if`, `try`, etc. *bodies* lazily because
        # those blocks DO run at import.  Function and class bodies do not.
        for sub in _iter_runtime_nodes(stmt):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id in _IO_NAMES:
                    findings.append((sub.lineno, func.id))
                elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    pair = (func.value.id, func.attr)
                    if pair in _IO_DOTTED_NAMES:
                        findings.append((sub.lineno, f"{pair[0]}.{pair[1]}"))
    return findings


def _iter_runtime_nodes(stmt: ast.stmt):
    """Yield every node from ``stmt`` that runs at module-import time.

    Skips function and class bodies (they only run when the function is called
    or the class is later instantiated -- those are deferred and out of scope
    for "side effects at import").
    """
    yield stmt
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return
    for child in ast.iter_child_nodes(stmt):
        yield from _iter_runtime_nodes(child)


def _find_top_level_import_star(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, module-name)`` for every top-level ``from X import *``."""
    if not isinstance(tree, ast.Module):
        return []
    return [
        (stmt.lineno, stmt.module or "")
        for stmt in tree.body
        if isinstance(stmt, ast.ImportFrom)
        for alias in stmt.names
        if alias.name == "*"
    ]


def _scan_python_file(py_path: Path, bundle_root: Path, errors: ExtensionErrorCollection) -> bool:
    """Scan a single .py file.  Returns whether it contributed a Component class."""
    rel = py_path.relative_to(bundle_root)
    try:
        source = py_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.add_error(
            ExtensionError(
                code="syntax-error",
                message=f"Could not read source: {exc}",
                location=str(rel),
                hint="Check file permissions / encoding.",
            )
        )
        return False
    try:
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError as exc:
        errors.add_error(
            ExtensionError(
                code="syntax-error",
                message=f"{exc.msg} (line {exc.lineno}, col {exc.offset})",
                location=str(rel),
                hint="Fix the syntax error before re-running validate.",
            )
        )
        return False

    # Top-level wildcard imports
    for lineno, modname in _find_top_level_import_star(tree):
        errors.add_error(
            ExtensionError(
                code="import-star-disallowed",
                message=(f"`from {modname} import *` is not permitted at module top level."),
                location=f"{rel}:{lineno}",
                content=f"from {modname} import *",
                hint=("Replace the wildcard with explicit names, or move the import inside a function body."),
            )
        )

    # Top-level I/O primitives
    for lineno, sym in _find_top_level_io(tree):
        errors.add_error(
            ExtensionError(
                code="top-level-io-disallowed",
                message=(f"Top-level I/O primitive {sym!r} runs on import; bundle modules must be import-safe."),
                location=f"{rel}:{lineno}",
                content=sym,
                hint=("Move the call inside a function body or guard it with ``if __name__ == '__main__'``."),
            )
        )

    # Component-class checks
    has_component = False
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef) and _is_component_class(node):
            has_component = True
            if not _has_build_method(node):
                errors.add_error(
                    ExtensionError(
                        code="build-method-missing",
                        message=(f"Component subclass {node.name!r} has no build() method."),
                        location=f"{rel}:{node.lineno}",
                        content=node.name,
                        hint=(
                            "Add a build() method to the component class. Components without build() cannot be invoked."
                        ),
                    )
                )
    return has_component


def _scan_bundle(bundle_name: str, bundle_root: Path, errors: ExtensionErrorCollection) -> _BundleAstSummary:
    """Scan all .py files under ``bundle_root``.  Updates ``errors`` in place.

    Symlinks are followed only when they stay inside ``bundle_root`` (so a
    symlinked ``vendored/`` subdir is fine, but a symlink to ``/etc/passwd``
    triggers ``path-escape`` and is excluded from the scan).
    """
    py_files: list[Path] = []
    for path in bundle_root.rglob("*.py"):
        if not is_within(path, bundle_root):
            errors.add_error(
                ExtensionError(
                    code="path-escape",
                    message=(f"Symlink {path} escapes the bundle directory."),
                    location=str(path.relative_to(bundle_root)),
                    content=str(path.relative_to(bundle_root)),
                    hint="Remove the symlink or point it at a path inside the bundle.",
                )
            )
            continue
        if path.is_file():
            py_files.append(path)

    has_component_anywhere = False
    for py in sorted(py_files):
        if _scan_python_file(py, bundle_root, errors):
            has_component_anywhere = True

    if not py_files:
        errors.add_error(
            ExtensionError(
                code="bundle-empty",
                message=f"Bundle {bundle_name!r} contains no Python source files.",
                location=str(bundle_root),
                content=bundle_name,
                hint="Add at least one Python module declaring a Component subclass.",
            )
        )
    elif not has_component_anywhere:
        errors.add_error(
            ExtensionError(
                code="no-component-subclass",
                message=(f"Bundle {bundle_name!r} has Python sources but no class appears to inherit from Component."),
                location=str(bundle_root),
                content=bundle_name,
                hint=("At least one module must declare a class whose base is Component (or ends with Component)."),
            )
        )
    return _BundleAstSummary(
        bundle_name=bundle_name,
        bundle_root=bundle_root,
        has_component_subclass=has_component_anywhere,
    )


# ---------------------------------------------------------------------------
# Pass 4 (opt-in): subprocess --execute-imports
# ---------------------------------------------------------------------------

# Environment variables that the import probe is allowed to inherit.  This is
# an allowlist (not a denylist) so untrusted bundle code cannot read cloud /
# CI credentials at import time even though the probe is running in a
# subprocess.  ``--execute-imports`` is best-effort hygiene, not a sandbox:
# the bundle code still executes Python with full process privileges, so
# stripping credential-bearing env vars is the minimum we can do to prevent
# trivial exfiltration by a top-level import.
_SUBPROCESS_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Required so Python itself can locate its stdlib, find shared libs,
        # resolve user-locale fallbacks, and locate UTF-8 codecs on Windows.
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_COLLATE",
        "LC_MESSAGES",
        "LC_NUMERIC",
        "LC_TIME",
        "LC_MONETARY",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "SYSTEMROOT",  # Windows: needed by os.path
        "WINDIR",  # Windows: needed by some libraries
        "TEMP",  # Windows TMP fallback
        "TMP",  # Windows TMP fallback
        "USERPROFILE",  # Windows HOME fallback
        # Common locale subset for non-glibc systems
        "TZ",
    }
)


def _build_probe_env(tmp_path: Path) -> dict[str, str]:
    """Return the env mapping passed to the validate probe subprocess.

    Allowlist approach: only well-known, non-credential-bearing variables
    inherit from the parent environment.  HOME, TMPDIR, and
    LANGFLOW_CONFIG_DIR are pinned to the throwaway temp directory so a
    misbehaving bundle cannot read or pollute the developer's real
    Langflow state.  Cloud credentials (AWS_*, OPENAI_API_KEY, GITHUB_TOKEN,
    ...) are intentionally NOT in the allowlist; without this, a malicious
    bundle's top-level import would read them and could exfiltrate.
    """
    env = {key: value for key, value in os.environ.items() if key in _SUBPROCESS_ENV_ALLOWLIST}
    env["HOME"] = str(tmp_path)
    env["TMPDIR"] = str(tmp_path)
    env["LANGFLOW_CONFIG_DIR"] = str(tmp_path / "config")
    # PATH is required for sys.executable to resolve loadable shared libraries
    # on macOS / Linux; if the parent has no PATH, fall back to a minimal one.
    if not env.get("PATH"):
        env["PATH"] = "/usr/bin:/bin"
    return env


_PROBE_SCRIPT_TEMPLATE = """
import importlib.util
import json
import sys
from pathlib import Path

bundle_root = Path({bundle_root!r})
results = []

for py in sorted(bundle_root.rglob("*.py")):
    rel = py.relative_to(bundle_root)
    if py.name == "__init__.py":
        continue
    spec = importlib.util.spec_from_file_location(
        f"_lfx_extension_probe.{{rel.with_suffix('').as_posix().replace('/', '.')}}",
        py,
    )
    if spec is None or spec.loader is None:
        results.append({{"path": str(rel), "error": "could not build module spec"}})
        continue
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001
        results.append({{"path": str(rel), "error": f"{{type(exc).__name__}}: {{exc}}"}})

print(json.dumps(results))
"""


def _run_execute_imports(
    bundle_name: str,
    bundle_root: Path,
    errors: ExtensionErrorCollection,
) -> None:
    """Run the bundle's modules in a clean subprocess and report failures.

    This is best-effort hygiene, not a security sandbox:
        - launch with a fresh CWD so the bundle can't pick up local config,
        - inherit an allowlist of env vars only (see ``_SUBPROCESS_ENV_ALLOWLIST``)
          so cloud / CI credentials cannot leak into untrusted bundle import,
        - point HOME / temp dirs at a throwaway directory.

    Network sandboxing is out of scope for v0 (per the ticket).  The bundle
    code still executes Python with full subprocess privileges, so do NOT
    rely on this for security review of untrusted code; treat it as a
    best-effort lint that surfaces import-time errors and prevents the most
    obvious credential leak.
    """
    with tempfile.TemporaryDirectory(prefix="lfx-extension-probe-") as tmp:
        tmp_path = Path(tmp)
        env = _build_probe_env(tmp_path)

        script = _PROBE_SCRIPT_TEMPLATE.format(bundle_root=str(bundle_root))
        try:
            result = subprocess.run(  # noqa: S603 - controlled args, see env above
                [sys.executable, "-I", "-c", script],
                cwd=str(tmp_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            errors.add_error(
                ExtensionError(
                    code="execute-imports-failed",
                    message=f"subprocess failed: {exc}",
                    location=str(bundle_root),
                    hint=("Re-run with --execute-imports after removing whatever is blocking subprocess startup."),
                )
            )
            return

        if result.returncode != 0:
            errors.add_error(
                ExtensionError(
                    code="execute-imports-failed",
                    message=(
                        f"probe exited with status {result.returncode}: "
                        f"{result.stderr.strip() or result.stdout.strip() or '(no output)'}"
                    ),
                    location=str(bundle_root),
                    hint=(
                        "Inspect the subprocess stderr above; usually a "
                        "missing dependency or top-level import-time error."
                    ),
                )
            )
            return

        try:
            import json as _json

            failures = _json.loads(result.stdout.strip() or "[]")
        except ValueError:
            errors.add_error(
                ExtensionError(
                    code="execute-imports-failed",
                    message="probe produced unparseable output",
                    location=str(bundle_root),
                    hint="Re-run with --verbose to see raw subprocess output.",
                )
            )
            return

        for failure in failures:
            errors.add_error(
                ExtensionError(
                    code="execute-imports-failed",
                    message=failure.get("error", "import failed"),
                    location=f"{bundle_name}:{failure.get('path', '<unknown>')}",
                    content=failure.get("path"),
                    hint=(
                        "Fix the import-time error in this module, or move the offending logic into a function body."
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def validate_extension(
    root: Path | str,
    *,
    execute_imports: bool = False,
) -> ValidateReport:
    """Validate an extension at ``root``.

    Args:
        root: Path to the extension directory (the directory containing the
            manifest, not the bundle itself).
        execute_imports: If True, additionally run each bundle module in a
            subprocess to surface import-time errors.  Default validate paths
            (``pack``, ``publish``, ``install``, registry ingest) MUST NOT
            pass this flag; it is for the author's own iteration loop.

    Returns:
        A :class:`ValidateReport`.  Callers should branch on ``report.ok``.
    """
    root_path = Path(root).resolve()
    report = ValidateReport(root=root_path)

    # Pass 1: discovery + schema
    source = _validate_manifest_phase(root_path, report)
    if source is None:
        return report

    manifest = source.manifest

    # Pass 2 + 3 per bundle.  v0 schema-validates length<=1 already, so this
    # loop runs once in practice; written generically so the plumbing is in
    # place when multi-bundle ships.
    for bundle in manifest.bundles:
        resolved, path_error = _resolve_bundle_path(root_path, bundle.path)
        if path_error is not None or resolved is None:
            if path_error is not None:
                report.errors.add_error(path_error)
            continue
        summary = _scan_bundle(bundle.name, resolved, report.errors)
        # Count files we actually scanned for ``bundle_files_scanned`` stat.
        report.bundle_files_scanned += sum(1 for _ in summary.bundle_root.rglob("*.py") if _.is_file())

        if execute_imports:
            _run_execute_imports(bundle.name, resolved, report.errors)

    return report
