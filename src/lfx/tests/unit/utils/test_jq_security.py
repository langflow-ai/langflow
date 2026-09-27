"""Tests for lfx.utils.jq_security.validate_jq_program.

Regression coverage for the jq $ENV / env server-environment disclosure: a
user-supplied jq program in the Data Operations / Parse JSON components must
never reach the process environment or read outside its input data.
"""

import pytest
from lfx.utils.jq_security import validate_jq_program


class TestRejectedPrograms:
    @pytest.mark.parametrize(
        "program",
        [
            # The PoC payloads: full environment disclosure.
            "$ENV",
            "env",
            "env.LANGFLOW_SECRET_KEY",
            "$ENV.LANGFLOW_SECRET_KEY",
            ". as $in | env",
            "{env: env}",
            # Hidden inside string interpolation (live jq code).
            '"\\(env)"',
            '"secret: \\($ENV.LANGFLOW_SECRET_KEY)"',
            '.data | "\\(env)"',
            # Dangerous builtin inside a nested interpolation is still live code.
            '"\\("\\(env)")"',
            # Object-key *shorthand* over a dangerous variable is not a key at
            # all: {$ENV} expands to {"ENV": $ENV} and discloses the environment.
            "{$ENV}",
            "{a: 1, $ENV}",
            # Key position exempts the key, never the value (the "{env: env}"
            # case above is the same rule seen from the other side).
            "{env: $ENV}",
            # A computed key is live code, not a key name.
            "{(env): 1}",
            '{"\\(env)": 1}',
            # Source-location information disclosure.
            "$__loc__",
            "def f: $__loc__; f",
            # Reading outside the component's declared input data.
            "input",
            "inputs",
            "[inputs]",
            # Definition aliasing does not launder the builtin.
            "def leak: env; leak",
        ],
    )
    def test_dangerous_programs_rejected(self, program):
        with pytest.raises(ValueError, match="not allowed"):
            validate_jq_program(program)

    @pytest.mark.parametrize("program", ["", None])
    def test_empty_program_rejected(self, program):
        with pytest.raises(ValueError, match="required"):
            validate_jq_program(program)

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="required"):
            validate_jq_program(123)


class TestAllowedPrograms:
    @pytest.mark.parametrize(
        "program",
        [
            ".",
            ".data",
            ".[0].key",
            ".properties.id",
            "keys",
            ".items[] | .name",
            # Field access on keys that happen to share a name with a builtin.
            ".env",
            ".environment",
            ".input",
            ".inputs",
            ".data.env.value",
            '.["env"]',
            '."env"',
            # User variables containing the substring are fine (jq is
            # case-sensitive; $ENV is the only dangerous spelling).
            "$env",
            ". as $env | $env",
            "$inputs",
            "$environment",
            # Identifiers merely containing the builtin name.
            ".my_input",
            ".envelope",
            ".getpath_from_config",
            # Object keys that happen to share a name with a builtin: these are
            # literal key names, not function references (LE-2550 follow-up).
            "{env: .a}",
            "{input: .a}",
            "{inputs: .a}",
            "{env : .a}",
            '{"env": .a}',
            "{a: .x, env: .y}",
            "{outer: {env: .a}}",
            "{env}",
            "{input}",
            ". as {env: $e} | $e",
            # getpath only indexes the value it is applied to.
            'getpath(["a", "b"])',
            '. | getpath(["data", "id"])',
            "getpath([.key])",
            # String-literal prose is not executable.
            '"env"',
            '"input data"',
            '.mode | select(. == "input")',
            '{label: "environment"}',
            # A nested interpolation closes without ending the outer one; the
            # remaining string text (here the literal word "env") is not code.
            '"\\("\\(.)") env"',
            # Comments are not executable.
            "# reads the env field\n.env",
            ".data # input payload",
        ],
    )
    def test_safe_programs_allowed(self, program):
        validate_jq_program(program)


class TestMasking:
    def test_string_contents_masked_but_interpolation_visible(self):
        from lfx.utils.jq_security import _mask_strings_and_comments

        masked = _mask_strings_and_comments('.a | "environment \\(env)" # env')
        assert "environment" not in masked
        assert masked.count("env") == 1  # only the interpolated one survives
        assert "\\(env)" in masked.replace(" ", "", 1) or "(env)" in masked

    def test_masking_preserves_length(self):
        from lfx.utils.jq_security import _mask_strings_and_comments

        program = '.a | "x\\"y \\(f(.))" # comment\n.b'
        assert len(_mask_strings_and_comments(program)) == len(program)


class TestObjectKeyMasking:
    """The key-position exemption must be positional, not a blanket allowance."""

    def test_key_masked_value_not(self):
        from lfx.utils.jq_security import _mask_object_keys, _mask_strings_and_comments

        masked = _mask_object_keys(_mask_strings_and_comments("{env: env}"))
        # Exactly one "env" survives: the one in value position.
        assert masked.count("env") == 1
        assert masked.endswith("env}")

    def test_masking_preserves_length(self):
        from lfx.utils.jq_security import _mask_object_keys

        program = '{env: .a, b: {input: [1, 2]}, c: "x"}'
        assert len(_mask_object_keys(program)) == len(program)

    def test_dollar_keys_left_visible(self):
        from lfx.utils.jq_security import _mask_object_keys

        assert "ENV" in _mask_object_keys("{$ENV}")
