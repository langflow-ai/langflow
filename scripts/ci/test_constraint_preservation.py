"""Regression test for release.yml's full -> base pre-release rewrite."""

import re

BASE_VERSION = "1.12.0rc3"
UPPER_BOUND = "1.13.dev0"


def rewrite_base_constraints(content: str) -> str:
    def replace_base(match: re.Match[str]) -> str:
        extras = match.group(1) or ""
        return f'"langflow-base{extras}>={BASE_VERSION},<{UPPER_BOUND}"'

    return re.sub(r'"langflow-base(\[[^]]+\])?[^";]*"', replace_base, content)


TEST_CASES = {
    '    "langflow-base~=1.12.0",': '    "langflow-base>=1.12.0rc3,<1.13.dev0",',
    'audio = ["langflow-base[audio]~=1.12.0"]': ('audio = ["langflow-base[audio]>=1.12.0rc3,<1.13.dev0"]'),
    'postgresql = ["langflow-base[postgresql]>=1.12.0,<1.13.dev0"]': (
        'postgresql = ["langflow-base[postgresql]>=1.12.0rc3,<1.13.dev0"]'
    ),
}


def test_all() -> None:
    for source, expected in TEST_CASES.items():
        output = rewrite_base_constraints(source)
        if output != expected:
            message = f"{source} -> {output}; expected {expected}"
            raise AssertionError(message)
    print("All base constraint preservation tests passed.")


if __name__ == "__main__":
    test_all()
