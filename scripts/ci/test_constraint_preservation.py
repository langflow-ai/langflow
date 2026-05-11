import subprocess

# Simulate the sed pattern from release.yml
# The pattern should preserve trailing commas
SED_PATTERN = 's|"langflow-base[^"]*"|"langflow-base[complete]>=0.8.0.rc3,<1.dev0"|g'

TEST_CASES = [
    '    "langflow-base[complete]~=0.8.0",',
    '    "langflow-base~=0.8.0",',
    '    "langflow-base[openai]~=0.8.0",',
    '    "langflow-base[complete]>=0.8.0,<1.dev0",',
    '    "langflow-base[complete]>=0.8.0.rc2,<1.dev0",',
]

EXPECTED = '    "langflow-base[complete]>=0.8.0.rc3,<1.dev0",'


def run_sed(input_line):
    """Run sed on input line and return the result."""
    # Use sed with stdin/stdout instead of file operations
    result = subprocess.run(  # noqa: S603
        ["sed", SED_PATTERN],  # noqa: S607
        input=input_line,
        capture_output=True,
        text=True,
        check=True,
    )
    # Use rstrip() to only remove trailing whitespace (newline), preserve leading spaces
    return result.stdout.rstrip()


def test_all():
    for i, case in enumerate(TEST_CASES):
        output = run_sed(case)
        if output != EXPECTED:
            msg = f"Test case {i + 1} failed: {case} → {output}"
            raise AssertionError(msg)
    print("All sed constraint preservation tests passed.")


if __name__ == "__main__":
    test_all()
