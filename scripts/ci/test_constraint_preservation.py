import os
import subprocess
import tempfile

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
        result = subprocess.check_output(["sed", SED_PATTERN, fname], text=True)
        return result.strip()
    finally:
        os.unlink(fname)


def test_all():
    for i, case in enumerate(TEST_CASES):
        output = run_sed(case)
        assert output == EXPECTED, f"Test case {i + 1} failed: {case} → {output}"
    print("All sed constraint preservation tests passed.")


if __name__ == "__main__":
    test_all()
