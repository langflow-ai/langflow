"""Regression test for release.yml's full -> core pre-release rewrite."""

import re

CORE_VERSION = "1.11.0rc3"
UPPER_BOUND = "1.12.dev0"


def rewrite_core_constraints(content: str) -> str:
    def replace_core(match: re.Match[str]) -> str:
        extras = match.group(1) or ""
        return f'"langflow-core{extras}>={CORE_VERSION},<{UPPER_BOUND}"'

    return re.sub(r'"langflow-core(\[[^]]+\])?[^";]*"', replace_core, content)


TEST_CASES = {
    '    "langflow-core~=1.11.0",': '    "langflow-core>=1.11.0rc3,<1.12.dev0",',
    'audio = ["langflow-core[audio]~=1.11.0"]': ('audio = ["langflow-core[audio]>=1.11.0rc3,<1.12.dev0"]'),
    'postgresql = ["langflow-core[postgresql]>=1.11.0,<1.12.dev0"]': (
        'postgresql = ["langflow-core[postgresql]>=1.11.0rc3,<1.12.dev0"]'
    ),
}


def test_all() -> None:
    for source, expected in TEST_CASES.items():
        output = rewrite_core_constraints(source)
        if output != expected:
            message = f"{source} -> {output}; expected {expected}"
            raise AssertionError(message)
    print("All core constraint preservation tests passed.")


if __name__ == "__main__":
    test_all()
