import ast
import contextlib
import functools
import importlib
import inspect
import threading
import warnings
from pathlib import Path
from typing import Optional, TypedDict, Union

from langchain_core._api.deprecation import LangChainDeprecationWarning
from pydantic import ValidationError

from lfx.custom.isolation import (
    DunderAccessTransformer,
    SecurityViolationError,
    create_isolated_builtins,
    create_isolated_import,
    execute_in_isolated_env,
)
from lfx.field_typing.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES, DEFAULT_IMPORT_STRING
from lfx.log.logger import logger


class ValidationErrors(TypedDict):
    """Structure for validation error results."""

    errors: list[str]


class ValidationResult(TypedDict):
    """Structure for validation results from validate_code."""

    imports: ValidationErrors
    function: ValidationErrors

# Cache for component index hash lookup map
_component_hash_cache: dict[str, set[str]] | None = None
_component_name_to_hash_cache: dict[str, str] | None = None
_cache_lock = threading.Lock()  # Protects cache initialization
_index_file_mtime: float | None = None  # Track index file modification time for staleness detection


def _get_index_file_path() -> Path | None:
    """Get the path to the built-in component index file, if it exists.
    
    Returns:
        Path to index file, or None if not found or not using built-in index.
    """
    try:
        import lfx
        pkg_dir = Path(inspect.getfile(lfx)).parent
        index_path = pkg_dir / "_assets" / "component_index.json"
        if index_path.exists():
            return index_path
    except Exception:  # noqa: BLE001
        pass
    return None


def _build_component_hash_cache() -> tuple[dict[str, set[str]], dict[str, str], float | None]:
    """Build hash lookup maps from component index for O(1) hash checking.

    Returns:
        Tuple of (hash_to_names_map, name_to_hash_map, index_file_mtime)
    """
    try:
        from lfx.interface.components import _read_component_index

        index = _read_component_index()
        if not index:
            return {}, {}, None

        hash_to_names: dict[str, set[str]] = {}
        name_to_hash: dict[str, str] = {}

        entries = index.get("entries", [])
        for _category_name, components_dict in entries:
            if not isinstance(components_dict, dict):
                continue
            for comp_name, comp_data in components_dict.items():
                if not isinstance(comp_data, dict):
                    continue
                metadata = comp_data.get("metadata", {})
                code_hash = metadata.get("code_hash")

                if code_hash:
                    # Map hash -> set of component names (for hash-only lookups)
                    if code_hash not in hash_to_names:
                        hash_to_names[code_hash] = set()
                    hash_to_names[code_hash].add(comp_name)

                    # Map component name -> hash (for name+hash lookups)
                    name_to_hash[comp_name] = code_hash

        # Get mtime of index file for staleness detection
        index_path = _get_index_file_path()
        mtime = index_path.stat().st_mtime if index_path and index_path.exists() else None

        return hash_to_names, name_to_hash, mtime
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Error building component hash cache: {e}")
        return {}, {}, None


def _get_component_hash_cache() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Get component hash cache, building it if necessary.
    
    Thread-safe: uses a lock to prevent race conditions during cache initialization.
    Checks index file mtime to detect staleness and rebuilds if the file changed.

    Returns:
        Tuple of (hash_to_names_map, name_to_hash_map)
    """
    global _component_hash_cache, _component_name_to_hash_cache, _index_file_mtime

    # Fast path: check if cache exists without lock (double-checked locking pattern)
    if _component_hash_cache is not None and _component_name_to_hash_cache is not None:
        # Check if index file has changed (only for built-in index)
        index_path = _get_index_file_path()
        if index_path and index_path.exists():
            try:
                current_mtime = index_path.stat().st_mtime
                if _index_file_mtime is not None and current_mtime != _index_file_mtime:
                    # File changed, need to rebuild
                    # Using != instead of > handles:
                    # - Filesystems with coarse timestamp resolution (same mtime after change)
                    # - Clock skew (mtime decreased)
                    # - File replacement scenarios
                    with _cache_lock:
                        # Double-check after acquiring lock
                        if _index_file_mtime is not None and current_mtime != _index_file_mtime:
                            _component_hash_cache = None
                            _component_name_to_hash_cache = None
                            _index_file_mtime = None
            except OSError:
                # File may have been deleted or is inaccessible, ignore
                pass
        
        # Return existing cache if still valid
        if _component_hash_cache is not None and _component_name_to_hash_cache is not None:
            return _component_hash_cache, _component_name_to_hash_cache

    # Slow path: acquire lock and build cache
    with _cache_lock:
        # Double-check after acquiring lock (another thread may have built it)
        if _component_hash_cache is None or _component_name_to_hash_cache is None:
            _component_hash_cache, _component_name_to_hash_cache, _index_file_mtime = _build_component_hash_cache()

    return _component_hash_cache, _component_name_to_hash_cache




def _is_core_component_impl(code_hash: str, component_name: str | None = None) -> bool:
    """Internal implementation of core component check.
    
    Args:
        code_hash: The hash of the component code
        component_name: Optional component name to look up in the index

    Returns:
        True if the component is a core component (matches index), False otherwise
    """
    try:
        # Get cached hash lookup maps
        hash_to_names, name_to_hash = _get_component_hash_cache()

        if component_name:
            # Fast path: Check if component_name exists and hash matches
            if component_name in name_to_hash:
                return name_to_hash[component_name] == code_hash
        # Fast path: Check if hash exists in cache (O(1) lookup)
        elif code_hash in hash_to_names:
            return True

        # No match found - it's a custom/edited component
        return False
    except Exception as e:  # noqa: BLE001
        # If anything goes wrong, assume it's custom (safer to validate)
        logger.debug(f"Error checking if component is core: {e}")
        return False


@functools.lru_cache(maxsize=512)
def _is_core_component(code_hash: str, component_name: str | None = None) -> bool:
    """Check if a component is a core component by comparing its code_hash with the component index.

    Core components have code_hash values that match entries in the component index.
    Custom/edited components have different code_hash values or don't exist in the index.

    This function uses cached hash lookup maps for O(1) performance instead of O(n) iteration.
    Results are cached by code_hash (not full code) to reduce memory pressure.
    
    Note: This function now expects code_hash instead of code. Use _is_core_component_by_code()
    if you have the raw code string.

    Args:
        code_hash: The hash of the component code
        component_name: Optional component name to look up in the index

    Returns:
        True if the component is a core component (matches index), False otherwise
    """
    return _is_core_component_impl(code_hash, component_name)


def _is_core_component_by_code(code: str, component_name: str | None = None) -> bool:
    """Check if a component is core by code string (convenience wrapper).
    
    This function generates the hash from code and calls _is_core_component.
    Use this when you have the raw code string.

    Args:
        code: The component source code
        component_name: Optional component name to look up in the index

    Returns:
        True if the component is a core component (matches index), False otherwise
    """
    try:
        from lfx.custom.utils import _generate_code_hash

        # Generate hash for the provided code
        code_hash = _generate_code_hash(code, component_name or "unknown")
        return _is_core_component(code_hash, component_name)
    except Exception as e:  # noqa: BLE001
        # If anything goes wrong, assume it's custom (safer to validate)
        logger.debug(f"Error checking if component is core: {e}")
        return False


def ensure_type_ignore() -> None:
    """Ensure TypeIgnore class exists on ast module for compatibility with older Python versions.
    
    This is needed when compiling AST modules with type_ignores=[] parameter.
    """
    if not hasattr(ast, "TypeIgnore"):

        class TypeIgnore(ast.AST):
            _fields = ()

        ast.TypeIgnore = TypeIgnore  # type: ignore[assignment, misc]


def validate_code(code: str, component_name: str | None = None, skip_isolation_for_core: bool = True) -> ValidationResult:
    """Validate user-provided code for security violations.

    This function performs three-phase validation:

    Phase 1: Module-level import validation
        - Checks all top-level imports (import X, from X import Y)
        - Blocks dangerous modules based on security level
        - Returns errors in errors["imports"]["errors"]

    Phase 2: Function/method body import validation (static analysis)
        - Statically analyzes function and method bodies for imports
        - Blocks dangerous imports that would execute at runtime
        - Handles nested functions, classes, and async functions
        - Returns errors in errors["function"]["errors"]

    Phase 3: Function definition execution (decorators, default args)
        - Executes function definitions in isolated environment
        - Blocks dangerous operations in decorators and default arguments
        - Transforms AST to prevent dunder access attacks
        - Returns errors in errors["function"]["errors"]

    Args:
        code: String containing Python code to validate
        component_name: Optional component name to check if it's a core component
        skip_isolation_for_core: If True, skip isolation validation for core components (default: True)

    Returns:
        ValidationResult: Dictionary with "imports" and "function" keys, each containing "errors" list
        Example: {"imports": {"errors": []}, "function": {"errors": []}}

    Note:
        Core components (those matching the component index) skip isolation validation
        and are allowed to use all builtins, as they are trusted Langflow components.
        Custom components are validated and executed in isolation to prevent security violations.
    """
    errors = {"imports": {"errors": []}, "function": {"errors": []}}

    if skip_isolation_for_core and _is_core_component_by_code(code, component_name):
        logger.debug(f"Skipping isolation validation for core component: {component_name}")
        return errors

    # Parse the code string into an abstract syntax tree (AST)
    try:
        tree = ast.parse(code)
    except Exception as e:  # noqa: BLE001
        logger.debug("Error parsing code", exc_info=True)
        errors["function"]["errors"].append(str(e))
        return errors

    # Ensure TypeIgnore exists for type_ignores field
    ensure_type_ignore()
    tree.type_ignores = []

    # Phase 1: Validate import statements (syntax check only, no code execution)
    # We use isolated_import to check if imports are valid and not blocked by security policy.
    # Note: We don't pass isolated_builtins_dict here because we're only validating imports,
    # not executing code. If someone tries `import builtins`, it will be blocked with an error.
    isolated_import = create_isolated_import()  # None = validation-only mode
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    # Use isolated import - blocks dangerous modules
                    isolated_import(alias.name, None, None, (), 0)
                except SecurityViolationError as e:
                    # SecurityViolationError means the module is blocked by security policy.
                    # We fail validation here so users get early feedback about blocked modules.
                    # This prevents code from passing validation but failing at runtime.
                    errors["imports"]["errors"].append(str(e))
                except ModuleNotFoundError as e:
                    errors["imports"]["errors"].append(str(e))
                except Exception as e:  # noqa: BLE001
                    errors["imports"]["errors"].append(str(e))
        elif isinstance(node, ast.ImportFrom):
            # Handle relative imports (level > 0) and absolute imports
            # For relative imports, node.module can be None (e.g., "from . import x")
            if node.level > 0:
                # Relative import - not allowed in custom components
                if node.names:
                    dots = "." * node.level
                    import_name = f"{dots}{node.names[0].name}"
                else:
                    dots = "." * node.level
                    import_name = f"{dots}{node.module or ''}".rstrip(".")
                errors["imports"]["errors"].append(
                    f"Relative import '{import_name}' (level {node.level}) is not allowed in custom components."
                )
            elif node.module:
                try:
                    # Use isolated import - blocks dangerous modules
                    isolated_import(node.module, None, None, (), 0)
                except SecurityViolationError as e:
                    # SecurityViolationError means the module is blocked by security policy.
                    # We fail validation here so users get early feedback about blocked modules.
                    # This prevents code from passing validation but failing at runtime.
                    errors["imports"]["errors"].append(str(e))
                except ModuleNotFoundError as e:
                    errors["imports"]["errors"].append(str(e))
                except Exception as e:  # noqa: BLE001
                    errors["imports"]["errors"].append(str(e))
            # else: ImportFrom with no module and level 0 - shouldn't happen, skip silently

    # Phase 2: Check for imports inside function/method bodies (static analysis)
    # Use efficient parent mapping to find containing functions in O(depth) instead of O(N²)
    isolated_import = create_isolated_import()
    
    # Build parent map: child -> parent in one pass
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    
    # Build function map: function node -> qualified name (e.g., "ClassName.method_name")
    func_map: dict[ast.FunctionDef | ast.AsyncFunctionDef, str] = {}  # function node -> qualified name
    
    def get_qualname(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Get qualified name for a function by walking up parent chain.
        
        Includes nested functions (e.g., "outer.inner") and class context (e.g., "Class.method.inner").
        Stops at module level or class definition.
        """
        parts = [func_node.name]
        current: ast.AST | None = func_node
        while current is not None:
            current = parents.get(current)
            if isinstance(current, ast.ClassDef):
                parts.append(current.name)
                break
            elif isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Include nested function names
                parts.append(current.name)
            elif isinstance(current, ast.Module):
                # Stop at module level
                break
        return ".".join(reversed(parts))
    
    # Build function map in one pass
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_map[node] = get_qualname(node)
    
    # Track module-level imports already checked in Phase 1 (direct children of tree.body)
    phase1_checked_imports = {n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))}
    
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        
        # Skip imports already checked in Phase 1
        if node in phase1_checked_imports:
            continue
        
        # Determine import context by walking up parent chain
        # Walk up to find the containing context (function, class, or module)
        current: ast.AST | None = node
        context_type: str | None = None
        owner_node: ast.AST | None = None
        
        while current is not None:
            parent = parents.get(current)
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                context_type = "function"
                owner_node = parent
                break
            elif isinstance(parent, ast.ClassDef):
                context_type = "class"
                owner_node = parent
                break
            elif isinstance(parent, ast.Module):
                context_type = "module"
                owner_node = parent
                break
            current = parent
        
        # Handle function-level imports (Phase 2)
        if context_type == "function" and owner_node and owner_node in func_map:
            containing_func = func_map[owner_node]
            
            # Determine import name first (before calling isolated_import which might raise)
            if isinstance(node, ast.Import):
                import_name = node.names[0].name if node.names else "unknown"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_name = node.module
                elif node.level > 0:
                    # Relative import - handle separately
                    if node.names:
                        dots = "." * node.level
                        import_name = f"{dots}{node.names[0].name}"
                    else:
                        dots = "." * node.level
                        import_name = f"{dots}{node.module or ''}".rstrip(".")
                    errors["function"]["errors"].append(
                        f"Function/method '{containing_func}' contains relative import '{import_name}' "
                        f"(level {node.level}). Relative imports are not allowed in custom components."
                    )
                    continue
                else:
                    # ImportFrom with no module and level 0 - shouldn't happen, but handle gracefully
                    import_name = node.names[0].name if node.names else "unknown"
            else:
                import_name = "unknown"
            
            # Check if import is blocked
            try:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        isolated_import(alias.name, None, None, (), 0)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    isolated_import(node.module, None, None, (), 0)
            except SecurityViolationError as e:
                errors["function"]["errors"].append(
                    f"Function/method '{containing_func}' contains blocked import '{import_name}': {e}"
                )
            except Exception:  # noqa: BLE001
                # Ignore other import errors (e.g., ModuleNotFoundError)
                pass
        
        # Handle module-level and class-body imports (validate with Phase 1 rules)
        # Class bodies execute at definition time, so treat them like module-level
        elif context_type in ("module", "class"):
            # Validate using Phase 1 rules (add to imports.errors)
            try:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        isolated_import(alias.name, None, None, (), 0)
                elif isinstance(node, ast.ImportFrom):
                    # Handle relative imports (level > 0) and absolute imports
                    if node.level > 0:
                        if node.names:
                            dots = "." * node.level
                            import_name = f"{dots}{node.names[0].name}"
                        else:
                            dots = "." * node.level
                            import_name = f"{dots}{node.module or ''}".rstrip(".")
                        errors["imports"]["errors"].append(
                            f"Relative import '{import_name}' (level {node.level}) is not allowed in custom components."
                        )
                    elif node.module:
                        isolated_import(node.module, None, None, (), 0)
            except SecurityViolationError as e:
                errors["imports"]["errors"].append(str(e))
            except ModuleNotFoundError as e:
                errors["imports"]["errors"].append(str(e))
            except Exception as e:  # noqa: BLE001
                errors["imports"]["errors"].append(str(e))

    # Phase 3: Transform AST to block dangerous dunder access, then execute function and class definitions
    # This actually runs the code (for decorators, default args, etc.) in an isolated environment.
    # Unlike Phase 1, this uses execute_in_isolated_env() which creates full isolation including
    # isolated builtins. This is where the real security isolation happens.
    #
    # CRITICAL: Transform AST to block dangerous dunder access before compilation
    # This prevents escapes like: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
    # We execute both FunctionDef and ClassDef nodes to match runtime behavior where class definitions
    # (including decorators and default arguments) are executed at definition time.
    transformer = DunderAccessTransformer()

    # Collect imports and definitions separately
    imports = []
    import_froms = []
    definitions = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom):
            import_froms.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append(node)

    if definitions:
        # Create isolated execution environment (shared across all definitions)
        # We prepend DEFAULT_IMPORT_STRING to match runtime (where it's also prepended)
        # This ensures decorators and default arguments have access to the same types
        # that would be available at runtime
        isolated_builtins_dict = create_isolated_builtins()
        isolated_import_func = create_isolated_import()
        exec_globals = {
            "__builtins__": isolated_builtins_dict,
            "__name__": "__main__",
            "__doc__": None,
            "__package__": None,
            "__import__": isolated_import_func,
        }

        # Execute DEFAULT_IMPORT_STRING first (matches runtime behavior)
        import_code = DEFAULT_IMPORT_STRING + "\n"
        import_module = ast.parse(import_code)
        import_code_obj = compile(import_module, "<string>", "exec")
        execute_in_isolated_env(import_code_obj, exec_globals)

        # Process imports from the code (needed for class definitions that inherit from Component, etc.)
        # This matches what prepare_global_scope does, but in isolation
        try:
            for node in imports:
                for alias in node.names:
                    module_name = alias.name
                    try:
                        module_obj = isolated_import_func(module_name, None, None, (), 0)
                    except SecurityViolationError:
                        # Import is blocked - skip it (already validated in Phase 1)
                        continue
                    # Set the variable name
                    if alias.asname:
                        exec_globals[alias.asname] = module_obj
                    else:
                        variable_name = module_name.split(".")[0]
                        exec_globals[variable_name] = isolated_import_func(variable_name, None, None, (), 0)

            for node in import_froms:
                if node.level > 0:
                    # Relative imports already validated in Phase 1/2, skip
                    continue
                if not node.module:
                    continue
                # Try langflow -> lfx replacement (matches prepare_global_scope behavior)
                module_names_to_try = [node.module]
                if node.module.startswith("langflow."):
                    lfx_module_name = node.module.replace("langflow.", "lfx.", 1)
                    module_names_to_try.append(lfx_module_name)

                success = False
                for module_name in module_names_to_try:
                    try:
                        imported_module = isolated_import_func(module_name, None, None, (), 0)
                        # Use _handle_module_attributes to properly handle attribute imports
                        _handle_module_attributes(imported_module, node, module_name, exec_globals, use_isolation=True)
                        success = True
                        break
                    except SecurityViolationError:
                        # Import is blocked - skip it (already validated in Phase 1)
                        continue
                    except ModuleNotFoundError:
                        continue
                
                if not success:
                    # If import failed, log but continue - definitions might still execute
                    logger.debug(f"Could not import {node.module} in Phase 3, continuing anyway")
        except Exception as e:  # noqa: BLE001
            # If imports fail, log but continue - definitions might still execute
            logger.debug("Error processing imports in Phase 3", exc_info=True)

        # Transform and execute all definitions together (matches prepare_global_scope behavior)
        combined_module = ast.Module(body=definitions, type_ignores=[])
        transformed_module = transformer.visit(combined_module)
        ast.fix_missing_locations(transformed_module)
        
        try:
            code_obj = compile(transformed_module, "<string>", "exec")
            execute_in_isolated_env(code_obj, exec_globals)
        except Exception as e:  # noqa: BLE001
            logger.debug("Error executing function/class definitions", exc_info=True)
            errors["function"]["errors"].append(str(e))

    # Return the errors dictionary
    return errors


def execute_function(code, function_name, *args, **kwargs):
    ensure_type_ignore()

    # Check if this is a core component - if so, skip isolation
    # Note: function_name might not match component name, so we check by hash only
    is_core = _is_core_component_by_code(code, None)

    try:
        module = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in function code: {e}") from e

    # Use prepare_global_scope to handle imports consistently with create_class
    try:
        exec_globals = prepare_global_scope(module, use_isolation=not is_core)
    except Exception as e:  # noqa: BLE001
        # Re-raise with context (could be SecurityViolationError, ModuleNotFoundError, etc.)
        raise ValueError(f"Error preparing execution environment for function '{function_name}': {e}") from e

    # Find the function definition
    try:
        function_code = next(
            node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
    except StopIteration:
        msg = f"Function '{function_name}' not found in code"
        raise ValueError(msg)

    function_code.parent = None
    
    try:
        if not is_core:
            # CRITICAL: Transform AST to block dangerous dunder access before compilation
            transformer = DunderAccessTransformer()
            transformed_func = transformer.visit(function_code)
            ast.fix_missing_locations(transformed_func)
            code_obj = compile(ast.Module(body=[transformed_func], type_ignores=[]), "<string>", "exec")
        else:
            code_obj = compile(ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec")
    except SyntaxError as e:
        raise ValueError(f"Syntax error compiling function '{function_name}': {e}") from e
    
    exec_locals = {}
    try:
        if is_core:
            exec(code_obj, exec_globals, exec_locals)
        else:
            # Execute in isolated environment
            execute_in_isolated_env(code_obj, exec_globals)
            # Extract the function from exec_globals after isolated execution
            if function_name not in exec_globals:
                msg = f"Function '{function_name}' was not created after execution (possible execution error)"
                raise ValueError(msg)
            exec_locals[function_name] = exec_globals[function_name]
    except SecurityViolationError as e:
        raise SecurityViolationError(f"Function '{function_name}' contains security violation: {e}") from e
    except ValueError:
        # Re-raise ValueError (function not found) as-is
        raise
    except Exception as exc:
        # Include original exception type and message for better debugging
        exc_type = type(exc).__name__
        msg = f"Error executing function '{function_name}': {exc_type}: {exc}"
        raise ValueError(msg) from exc

    # Add the function to the exec_globals dictionary
    exec_globals[function_name] = exec_locals[function_name]

    return exec_globals[function_name](*args, **kwargs)


def create_function(code, function_name):
    ensure_type_ignore()

    # Check if this is a core component - if so, skip isolation
    # Note: function_name might not match component name, so we check by hash only
    is_core = _is_core_component_by_code(code, None)

    try:
        module = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in function code: {e}") from e

    # Use prepare_global_scope to handle imports consistently with create_class
    try:
        exec_globals = prepare_global_scope(module, use_isolation=not is_core)
    except Exception as e:  # noqa: BLE001
        # Re-raise with context (could be SecurityViolationError, ModuleNotFoundError, etc.)
        raise ValueError(f"Error preparing execution environment for function '{function_name}': {e}") from e

    # Find the function definition
    try:
        function_code = next(
            node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
    except StopIteration:
        msg = f"Function '{function_name}' not found in code"
        raise ValueError(msg)

    function_code.parent = None
    
    try:
        if not is_core:
            # CRITICAL: Transform AST to block dangerous dunder access before compilation
            transformer = DunderAccessTransformer()
            transformed_func = transformer.visit(function_code)
            ast.fix_missing_locations(transformed_func)
            code_obj = compile(ast.Module(body=[transformed_func], type_ignores=[]), "<string>", "exec")
        else:
            code_obj = compile(ast.Module(body=[function_code], type_ignores=[]), "<string>", "exec")
    except SyntaxError as e:
        raise ValueError(f"Syntax error compiling function '{function_name}': {e}") from e
    
    exec_locals = {}
    execution_error: Exception | None = None
    try:
        if is_core:
            exec(code_obj, exec_globals, exec_locals)
        else:
            # Execute in isolated environment
            execute_in_isolated_env(code_obj, exec_globals)
            # Extract the function from exec_globals after isolated execution
            if function_name in exec_globals:
                exec_locals[function_name] = exec_globals[function_name]
    except SecurityViolationError as e:
        raise SecurityViolationError(f"Function '{function_name}' contains security violation: {e}") from e
    except Exception as exc:  # noqa: BLE001
        # Store execution error but don't raise yet - check if function was created anyway
        execution_error = exc

    if function_name not in exec_locals and function_name not in exec_globals:
        if execution_error:
            # Function wasn't created due to execution error
            exc_type = type(execution_error).__name__
            msg = f"Function '{function_name}' was not created due to execution error: {exc_type}: {execution_error}"
            raise ValueError(msg) from execution_error
        else:
            # Function simply not found (shouldn't happen if StopIteration was caught, but handle gracefully)
            msg = f"Function '{function_name}' not found in code after execution"
            raise ValueError(msg)

    exec_globals[function_name] = exec_locals.get(function_name) or exec_globals.get(function_name)

    # Return a function that imports necessary modules and calls the target function
    def wrapped_function(*args, **kwargs):
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        return exec_globals[function_name](*args, **kwargs)

    return wrapped_function


def create_class(code, class_name):
    """Dynamically create a class from a string of code and a specified class name.

    Args:
        code: String containing the Python code defining the class
        class_name: Name of the class to be created

    Returns:
         A function that, when called, returns an instance of the created class

    Raises:
        ValueError: If the code contains syntax errors or the class definition is invalid
    """
    ensure_type_ignore()

    # Check if this is a core component BEFORE modifying code (hash must match original)
    is_core = _is_core_component_by_code(code, class_name)

    code = code.replace("from langflow import CustomComponent", "from langflow.custom import CustomComponent")
    code = code.replace(
        "from langflow.interface.custom.custom_component import CustomComponent",
        "from langflow.custom import CustomComponent",
    )

    code = DEFAULT_IMPORT_STRING + "\n" + code

    try:
        module = ast.parse(code)
        exec_globals = prepare_global_scope(module, use_isolation=not is_core)

        class_code = extract_class_code(module, class_name)
        
        if not is_core:
            # CRITICAL: Transform AST to block dangerous dunder access before compilation
            # This prevents escapes in class bodies, decorators, and default values
            transformer = DunderAccessTransformer()
            transformed_class = transformer.visit(class_code)
            ast.fix_missing_locations(transformed_class)
            compiled_class = compile(ast.Module(body=[transformed_class], type_ignores=[]), "<string>", "exec")
        else:
            compiled_class = compile_class_code(class_code)

        return build_class_constructor(compiled_class, exec_globals, class_name, use_isolation=not is_core)

    except SyntaxError as e:
        msg = f"Syntax error in code: {e!s}"
        raise ValueError(msg) from e
    except NameError as e:
        msg = f"Name error (possibly undefined variable): {e!s}"
        raise ValueError(msg) from e
    except ValidationError as e:
        messages = [error["msg"].split(",", 1) for error in e.errors()]
        error_message = "\n".join([message[1] if len(message) > 1 else message[0] for message in messages])
        raise ValueError(error_message) from e
    except Exception as e:
        msg = f"Error creating class. {type(e).__name__}({e!s})."
        raise ValueError(msg) from e


def _import_module_with_warnings(module_name: str) -> object:
    """Import module with appropriate warning suppression."""
    if "langchain" in module_name:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", LangChainDeprecationWarning)
            return importlib.import_module(module_name)
    else:
        return importlib.import_module(module_name)


def _handle_module_attributes(imported_module, node, module_name, exec_globals, use_isolation: bool = False):
    """Handle importing specific attributes from a module."""
    for alias in node.names:
        try:
            # First try getting it as an attribute
            exec_globals[alias.name] = getattr(imported_module, alias.name)
        except AttributeError:
            # If that fails, try importing the full module path
            full_module_path = f"{module_name}.{alias.name}"
            if use_isolation:
                # Use isolated import - blocks dangerous modules
                isolated_import_func = exec_globals.get("__import__")
                if not isolated_import_func:
                    raise RuntimeError("Isolation not properly set up: __import__ not found in exec_globals")
                try:
                    exec_globals[alias.name] = isolated_import_func(full_module_path, None, None, (), 0)
                except SecurityViolationError as e:
                    raise SecurityViolationError(f"Component contains blocked import '{full_module_path}': {e}") from e
            else:
                exec_globals[alias.name] = importlib.import_module(full_module_path)


def prepare_global_scope(module, use_isolation: bool = False) -> dict[str, object]:
    """Prepares the global scope with necessary imports from the provided code module.

    Args:
        module: AST parsed module
        use_isolation: If True, use isolated imports (blocks dangerous modules). If False, use direct imports.

    Returns:
        Dictionary representing the global scope with imported modules

    Raises:
        ModuleNotFoundError: If a module is not found in the code
        SecurityViolationError: If a blocked module is imported and use_isolation is True
    """
    ensure_type_ignore()
    
    if use_isolation:
        # Create isolated builtins and import function for runtime isolation
        isolated_builtins_dict = create_isolated_builtins()
        isolated_import_func = create_isolated_import()
        exec_globals = {
            "__builtins__": isolated_builtins_dict,
            "__name__": "__main__",
            "__doc__": None,
            "__package__": None,
            "__import__": isolated_import_func,
        }
    else:
        # For core components, use standard Python execution
        # Ensure __import__ is available for runtime imports in function bodies
        exec_globals = globals().copy()
        # Make __import__ explicitly available (normally comes from __builtins__)
        if "__import__" not in exec_globals:
            exec_globals["__import__"] = importlib.__import__
    
    imports = []
    import_froms = []
    definitions = []

    for node in module.body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            import_froms.append(node)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign)):
            definitions.append(node)

    for node in imports:
        for alias in node.names:
            module_name = alias.name
            if use_isolation:
                # Use isolated import - blocks dangerous modules
                try:
                    module_obj = isolated_import_func(module_name, None, None, (), 0)
                except SecurityViolationError as e:
                    raise SecurityViolationError(f"Component contains blocked import '{alias.name}': {e}") from e
            else:
                # Import the full module path to ensure submodules are loaded
                module_obj = importlib.import_module(module_name)

            # Determine the variable name
            if alias.asname:
                # For aliased imports like "import yfinance as yf", use the imported module directly
                variable_name = alias.asname
                exec_globals[variable_name] = module_obj
            else:
                # For dotted imports like "urllib.request", set the variable to the top-level package
                variable_name = module_name.split(".")[0]
                if use_isolation:
                    # For isolated imports, we already have the module_obj, but for dotted imports
                    # we need to get the top-level package
                    try:
                        exec_globals[variable_name] = isolated_import_func(variable_name, None, None, (), 0)
                    except SecurityViolationError as e:
                        raise SecurityViolationError(f"Component contains blocked import '{variable_name}': {e}") from e
                else:
                    exec_globals[variable_name] = importlib.import_module(variable_name)

    for node in import_froms:
        module_names_to_try = [node.module]

        # If original module starts with langflow, also try lfx equivalent
        if node.module and node.module.startswith("langflow."):
            lfx_module_name = node.module.replace("langflow.", "lfx.", 1)
            module_names_to_try.append(lfx_module_name)

        success = False
        last_error = None

        for module_name in module_names_to_try:
            try:
                if use_isolation:
                    # Use isolated import - blocks dangerous modules
                    imported_module = isolated_import_func(module_name, None, None, (), 0)
                else:
                    imported_module = _import_module_with_warnings(module_name)
                _handle_module_attributes(imported_module, node, module_name, exec_globals, use_isolation)

                success = True
                break

            except SecurityViolationError as e:
                # Security violation - module is blocked
                raise SecurityViolationError(f"Component contains blocked import '{node.module}': {e}") from e
            except ModuleNotFoundError as e:
                last_error = e
                continue

        if not success:
            # Re-raise the last error to preserve the actual missing module information
            if last_error:
                raise last_error
            msg = f"Module {node.module} not found. Please install it and try again"
            raise ModuleNotFoundError(msg)

    if definitions:
        combined_module = ast.Module(body=definitions, type_ignores=[])
        
        if use_isolation:
            # CRITICAL: Transform AST to block dangerous dunder access before compilation
            # This prevents escapes like: ().__class__.__bases__[0].__subclasses__()[XX].__init__.__globals__['os']
            # Applies to ClassDef bodies, module-level assignments, and class decorators
            transformer = DunderAccessTransformer()
            transformed_module = transformer.visit(combined_module)
            ast.fix_missing_locations(transformed_module)
            compiled_code = compile(transformed_module, "<string>", "exec")
            # Execute in isolated environment
            execute_in_isolated_env(compiled_code, exec_globals)
        else:
            compiled_code = compile(combined_module, "<string>", "exec")
            exec(compiled_code, exec_globals)

    return exec_globals


def extract_class_code(module, class_name) -> ast.ClassDef:
    """Extracts the AST node for the specified class from the module.

    Args:
        module: AST parsed module
        class_name: Name of the class to extract

    Returns:
        AST node of the specified class
    """
    class_code = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)

    class_code.parent = None
    return class_code


def compile_class_code(class_code):
    """Compiles the AST node of a class into a code object.

    Args:
        class_code: AST node of the class

    Returns:
        Compiled code object of the class
    """
    ensure_type_ignore()
    return compile(ast.Module(body=[class_code], type_ignores=[]), "<string>", "exec")


def build_class_constructor(compiled_class, exec_globals, class_name, use_isolation: bool = False):
    """Builds a constructor function for the dynamically created class.

    Args:
        compiled_class: Compiled code object of the class
        exec_globals: Global scope with necessary imports
        class_name: Name of the class
        use_isolation: If True, execute in isolated environment. If False, use direct exec.

    Returns:
         Constructor function for the class
    """
    exec_locals = {}
    if use_isolation:
        # Execute in isolated environment for custom components
        execute_in_isolated_env(compiled_class, exec_globals)
        # Extract the class from exec_globals after isolated execution
        if class_name not in exec_globals:
            msg = f"Class '{class_name}' not found after execution"
            raise ValueError(msg)
        exec_globals[class_name] = exec_globals[class_name]
    else:
        # Core components use direct exec
        exec(compiled_class, exec_globals, exec_locals)
        exec_globals[class_name] = exec_locals[class_name]

    # Return a function that imports necessary modules and creates an instance of the target class
    def build_custom_class():
        for module_name, module in exec_globals.items():
            if isinstance(module, type(importlib)):
                globals()[module_name] = module

        return exec_globals[class_name]

    return build_custom_class()

def find_names_in_code(code, names):
    """Finds if any of the specified names are present in the given code string.

    Args:
        code: The source code as a string.
        names: A list of names to check for in the code.

    Returns:
        A set of names that are found in the code.
    """
    return {name for name in names if name in code}


def extract_function_name(code):
    module = ast.parse(code)
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    msg = "No function definition found in the code string"
    raise ValueError(msg)


def extract_class_name(code: str) -> str:
    """Extract the name of the first Component subclass found in the code.

    Args:
        code (str): The source code to parse

    Returns:
        str: Name of the first Component subclass found

    Raises:
        TypeError: If no Component subclass is found in the code
    """
    try:
        module = ast.parse(code)
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue

            # Check bases for Component inheritance
            # TODO: Build a more robust check for Component inheritance
            for base in node.bases:
                if isinstance(base, ast.Name) and any(pattern in base.id for pattern in ["Component", "LC"]):
                    return node.name

        msg = f"No Component subclass found in the code string. Code snippet: {code[:100]}"
        raise TypeError(msg)
    except SyntaxError as e:
        msg = f"Invalid Python code: {e!s}"
        raise ValueError(msg) from e
