import subprocess
import tempfile
from pathlib import Path

# Simulate the sed pattern from release.yml
SED_PATTERN = 's|"langflow-base[^"]*"|"langflow-base[complete]>=0.8.0.rc3,<1.dev0"|'

TEST_CASES = [
    '    "langflow-base[complete]~=0.8.0",',
    '    "langflow-base~=0.8.0",',
    '    "langflow-base[openai]~=0.8.0",',
    '    "langflow-base[complete]>=0.8.0,<1.dev0",',
    '    "langflow-base[complete]>=0.8.0.rc2,<1.dev0",',
]

EXPECTED = '    "langflow-base[complete]>=0.8.0.rc3,<1.dev0",'


def run_sed(input_line):
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(input_line + "\n")
        fname = f.name
    try:
        # Use absolute path for sed
        sed_path = subprocess.run(
            ["which", "sed"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        result = subprocess.run(
            [sed_path, SED_PATTERN, fname],  # noqa: S603
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    finally:
        Path(fname).unlink()


def test_all():
    for i, case in enumerate(TEST_CASES):
        output = run_sed(case)
        if output != EXPECTED:
            msg = f"Test case {i+1} failed: {case} → {output}"
            raise AssertionError(msg)
    print("All sed constraint preservation tests passed.")


if __name__ == "__main__":
    test_all()

# Made with Bob
