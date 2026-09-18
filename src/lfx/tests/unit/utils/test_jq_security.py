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
            # Source-location information disclosure.
            "$__loc__",
            "def f: $__loc__; f",
            # Reading outside the component's declared input data.
            "input",
            "inputs",
            "[inputs]",
            "getpath",
            'getpath(["data"])',
            '. as $x | getpath(["a"])',
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
            # String-literal prose is not executable.
            '"env"',
            '"input data"',
            '.mode | select(. == "input")',
            '{label: "environment"}',
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
