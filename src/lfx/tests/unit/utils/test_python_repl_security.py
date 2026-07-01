"""Unit tests for the Python REPL hardening helpers."""

import pytest
from lfx.utils.python_repl_security import safe_builtins, validate_code_safety


class TestSafeBuiltins:
    def test_excludes_dangerous_builtins(self):
        """Code-execution, import, filesystem and introspection builtins are removed."""
        builtins_map = safe_builtins()
        for name in (
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "globals",
            "locals",
            "vars",
            "getattr",
            "setattr",
            "delattr",
            "breakpoint",
            "memoryview",
            "exit",
            "quit",
            "help",
        ):
            assert name not in builtins_map, f"{name} must not be exposed"

    def test_includes_common_safe_builtins(self):
        """Common, safe builtins remain available so normal code keeps working."""
        builtins_map = safe_builtins()
        for name in (
            "print",
            "len",
            "range",
            "int",
            "float",
            "str",
            "list",
            "dict",
            "tuple",
            "set",
            "sum",
            "min",
            "max",
            "sorted",
            "enumerate",
            "zip",
            "isinstance",
            "type",
            "Exception",
            "ValueError",
        ):
            assert name in builtins_map, f"{name} should be available"

    def test_returns_fresh_copy(self):
        """Each call returns an independent dict so callers cannot mutate shared state."""
        first = safe_builtins()
        first["injected"] = object()
        assert "injected" not in safe_builtins()


class TestValidateCodeSafety:
    @pytest.mark.parametrize(
        "code",
        [
            "import os",
            "import subprocess",
            "from os import system",
            "().__class__",
            "[].__class__.__bases__[0].__subclasses__()",
            "(lambda: 0).__globals__",
            "().__class__.__mro__",
            "(x for x in []).gi_frame",
            "object.__subclasses__()",
            'f"{().__class__}"',
            "int.mro()",
            '"{0.__globals__}".format(f)',
            '"{0[__builtins__]}".format(f)',
            '"{0.__class__}".format(obj)',
            "'{0}'.format(1)",
            "'{name}'.format_map({'name': 'x'})",
            "template = '{0.' + 'value' + '}'\ntemplate.format(obj)",
            # Sibling formatter sinks that carry the dunder chain in a *string* argument
            # (invisible to the AST attribute check) — blocked via the method name.
            'string.Formatter().vformat("{0.__globals__[os].environ[SECRET]}", (f,), {})',
            'string.Formatter().get_field("0.__loader__.find_spec.__globals__[sys]", (f,), {})',
            "string.Formatter().get_value(0, (f,), {})",
            'operator.attrgetter("__globals__")(f)',
            # ``operator.methodcaller`` defers a method name to call time, so a
            # runtime-assembled template (no literal "{...__" for the regex to catch)
            # reaches str.format/format_map invisibly. Blocked via the factory name.
            'operator.methodcaller("format", f)(tmpl)',
            'operator.methodcaller("format_map", d)(tmpl)',
            'operator.methodcaller("__getattribute__", "__globals__")(f)',
            # A literal dunder-bearing template reaches a non-blocked formatter via a var;
            # the literal-field scan rejects the template regardless of the consumer.
            't = "{0.__globals__}"\nstring.Formatter().vformat(t, (f,), {})',
        ],
    )
    def test_blocks_escape_and_import(self, code):
        """Inline imports, escape gadgets, and formatter method access are rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    @pytest.mark.parametrize(
        "code",
        [
            "print('Hello, World!')",
            "print(len([1, 2, 3]))",
            "x = 1\ny = x + 2\nprint(y)",
            "math.sqrt(16)",
            "result = [i * 2 for i in range(5)]\nprint(sum(result))",
            "data = {'a': 1, 'b': 2}\nprint(sorted(data.items()))",
            "name = 'x'\nprint(f'{name}')",
            "print(format(3.14159, '.2f'))",
        ],
    )
    def test_allows_safe_code(self, code):
        """Ordinary code (no imports, no dunder/frame access) is allowed."""
        validate_code_safety(code)  # should not raise

    def test_syntax_error_propagates(self):
        """Unparseable code surfaces a SyntaxError to the caller."""
        with pytest.raises(SyntaxError):
            validate_code_safety("print('unterminated")


class TestFormatterSinkBypassesAreBlocked:
    """Env-canary regression for the sibling-formatter sandbox bypass.

    ``str.format``/``format_map`` are not the only formatter sinks: the same
    ``__globals__`` traversal lives in a *string* argument (invisible to the AST
    attribute check) when fed through ``string.Formatter`` traversal primitives,
    ``operator.attrgetter`` or ``operator.methodcaller``. Each test first proves the
    gadget *does* leak an env var canary when run unguarded, then asserts
    ``validate_code_safety`` rejects the exact input before it could execute.
    """

    @staticmethod
    def _func_with_os():
        """A function whose ``__globals__`` deterministically contains ``os``.

        The gadget escapes via ``func.__globals__[os]``, so the precondition only leaks
        when ``os`` is bound in the function's module globals. Building the function with
        an explicit globals dict makes the leak reproducible regardless of which modules
        this test file happens to import.
        """
        import os

        namespace = {"os": os}
        exec("def _f():\n    return 0", namespace)  # noqa: S102 - test-only controlled exec
        return namespace["_f"]

    def test_formatter_vformat_bypass(self, monkeypatch):
        """``string.Formatter().vformat`` reaches os.environ; the call is blocked."""
        import string

        monkeypatch.setenv("LFX_REPL_CANARY", "SHOULD_NOT_LEAK")
        leaked = string.Formatter().vformat("{0.__globals__[os].environ[LFX_REPL_CANARY]}", (self._func_with_os(),), {})
        assert leaked == "SHOULD_NOT_LEAK"  # gadget is real when unguarded

        code = 'string.Formatter().vformat("{0.__globals__[os].environ[LFX_REPL_CANARY]}", (f,), {})'
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    def test_formatter_get_field_bypass(self, monkeypatch):
        """``string.Formatter().get_field`` traverses a dotted path; the call is blocked."""
        import string

        monkeypatch.setenv("LFX_REPL_CANARY", "SHOULD_NOT_LEAK")
        obj, _ = string.Formatter().get_field("0.__globals__[os].environ[LFX_REPL_CANARY]", (self._func_with_os(),), {})
        assert obj == "SHOULD_NOT_LEAK"  # gadget is real when unguarded

        code = 'string.Formatter().get_field("0.__globals__[os].environ[LFX_REPL_CANARY]", (f,), {})'
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    def test_operator_attrgetter_bypass(self, monkeypatch):
        """``operator.attrgetter('__globals__')`` reaches os.environ; the call is blocked."""
        import operator

        monkeypatch.setenv("LFX_REPL_CANARY", "SHOULD_NOT_LEAK")
        leaked = operator.attrgetter("__globals__")(self._func_with_os())["os"].environ["LFX_REPL_CANARY"]
        assert leaked == "SHOULD_NOT_LEAK"  # gadget is real when unguarded

        code = 'operator.attrgetter("__globals__")(f)'
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    def test_operator_methodcaller_format_bypass(self, monkeypatch):
        """``operator.methodcaller('format', f)`` invokes str.format on a runtime template.

        Unlike a literal ``"{0.__globals__}".format(f)``, the template is assembled at
        runtime so the ``_FORMAT_FIELD_DUNDER_RE`` literal scan never sees ``{...__``,
        and ``methodcaller`` keeps the method name ``"format"`` in a *string* argument so
        there is no ``ast.Attribute`` named ``format`` either. Blocking the ``methodcaller``
        factory name is what rejects it.
        """
        import operator

        monkeypatch.setenv("LFX_REPL_CANARY", "SHOULD_NOT_LEAK")
        # Template built from fragments at runtime — invisible to the literal-field scan.
        tmpl = "{0." + "__globals__" + "[os].environ[LFX_REPL_CANARY]}"
        leaked = operator.methodcaller("format", self._func_with_os())(tmpl)
        assert leaked == "SHOULD_NOT_LEAK"  # gadget is real when unguarded

        code = 'operator.methodcaller("format", f)(tmpl)'
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    def test_operator_methodcaller_getattribute_bypass(self, monkeypatch):
        """``methodcaller('__getattribute__', '__globals__')`` reaches an attr by string name.

        ``methodcaller`` can invoke *any* method — including ``__getattribute__`` — with the
        attribute name supplied as a runtime string, bypassing the dunder-attribute AST
        check. Blocked via the ``methodcaller`` factory name.
        """
        import operator

        monkeypatch.setenv("LFX_REPL_CANARY", "SHOULD_NOT_LEAK")
        leaked = operator.methodcaller("__getattribute__", "__globals__")(self._func_with_os())["os"].environ[
            "LFX_REPL_CANARY"
        ]
        assert leaked == "SHOULD_NOT_LEAK"  # gadget is real when unguarded

        code = 'operator.methodcaller("__getattribute__", "__globals__")(f)'
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)


class TestEnsureCodeExecutionEnabled:
    """GHSA-8qpj-27x8-pwpq: code execution honors allow_custom_components."""

    def test_blocks_when_custom_components_disabled(self, monkeypatch):
        from types import SimpleNamespace

        from lfx.utils.python_repl_security import CodeExecutionDisabledError, ensure_code_execution_enabled

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False)),
        )
        with pytest.raises(CodeExecutionDisabledError):
            ensure_code_execution_enabled()

    def test_allows_when_custom_components_enabled(self, monkeypatch):
        from types import SimpleNamespace

        from lfx.utils.python_repl_security import ensure_code_execution_enabled

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
        )
        ensure_code_execution_enabled()  # must not raise

    def test_allows_when_services_layer_absent(self, monkeypatch):
        """An absent services layer (ImportError) is a local/trusted context -> allowed."""
        from lfx.utils.python_repl_security import ensure_code_execution_enabled

        # Deleting the imported name makes ``from lfx.services.deps import
        # get_settings_service`` raise ImportError, simulating an absent services layer.
        monkeypatch.delattr("lfx.services.deps.get_settings_service")
        ensure_code_execution_enabled()  # must not raise

    def test_blocks_when_settings_service_is_none(self, monkeypatch):
        """A None settings service (registered-but-failed stack) fails closed, not open."""
        from lfx.utils.python_repl_security import CodeExecutionDisabledError, ensure_code_execution_enabled

        # get_service swallows init errors into None; the gate must refuse, not bypass.
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        with pytest.raises(CodeExecutionDisabledError):
            ensure_code_execution_enabled()

    def test_non_import_error_propagates(self, monkeypatch):
        """A non-ImportError from get_settings_service() propagates, never failing open."""
        from lfx.utils.python_repl_security import ensure_code_execution_enabled

        # Only ImportError means "no services layer"; anything else must surface.
        def _boom():
            error = "settings stack exploded"
            raise RuntimeError(error)

        monkeypatch.setattr("lfx.services.deps.get_settings_service", _boom)
        with pytest.raises(RuntimeError, match="settings stack exploded"):
            ensure_code_execution_enabled()
