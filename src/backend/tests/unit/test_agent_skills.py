"""Tests for .agents/skills/ directory structure, SKILL.md frontmatter, and reference files.

These tests validate that all agent skill files added in the PR are well-formed,
have required sections, cross-references resolve, and template files contain
the expected patterns.
"""

import re
from pathlib import Path

import pytest

# Root of the repository
REPO_ROOT = Path(__file__).parents[4]
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"

# Expected skill directories (all added in this PR)
EXPECTED_SKILLS = [
    "backend-code-review",
    "component-refactoring",
    "e2e-testing",
    "frontend-code-review",
    "frontend-query-mutation",
    "frontend-testing",
]

# Required frontmatter keys in every SKILL.md that has frontmatter
SKILL_REQUIRED_FRONTMATTER_KEYS = ["name", "description"]

# Skills that have YAML frontmatter (the frontend-testing SKILL.md intentionally omits it)
SKILLS_WITH_FRONTMATTER = [
    "backend-code-review",
    "component-refactoring",
    "e2e-testing",
    "frontend-code-review",
    "frontend-query-mutation",
]

# Per-skill "when to use" section heading (each skill uses a different phrasing)
SKILL_WHEN_TO_USE_HEADINGS: dict[str, str] = {
    "backend-code-review": "## When to use this skill",
    "component-refactoring": "## Quick Reference",  # uses Quick Reference as the entry point
    "e2e-testing": "## When to Apply",
    "frontend-code-review": "## When to use this skill",
    "frontend-query-mutation": "## Intent",
    "frontend-testing": "## When to Apply",
}

# Per-skill required sections (in addition to the common ones)
SKILL_SPECIFIC_SECTIONS: dict[str, list[str]] = {
    "backend-code-review": [
        "## How to use this skill",
        "## Checklist",
        "## General Review Rules",
        "## Required Output Format",
    ],
    "component-refactoring": [
        "## Core Refactoring Patterns",
        "## Refactoring Workflow",
    ],
    "e2e-testing": [],
    "frontend-code-review": [
        "## Checklist",
        "## Required Output Format",
    ],
    "frontend-query-mutation": [],
    "frontend-testing": [],
}

# Per-skill expected reference files
SKILL_REFERENCE_FILES: dict[str, list[str]] = {
    "backend-code-review": [
        "references/architecture-rule.md",
        "references/db-schema-rule.md",
        "references/repositories-rule.md",
        "references/sqlalchemy-rule.md",
    ],
    "component-refactoring": [
        "references/complexity-patterns.md",
        "references/component-splitting.md",
        "references/hook-extraction.md",
    ],
    "e2e-testing": [
        "references/fixtures.md",
        "references/helpers.md",
        "references/selectors.md",
    ],
    "frontend-code-review": [
        "references/business-logic.md",
        "references/code-quality.md",
        "references/performance.md",
    ],
    "frontend-query-mutation": [
        "references/query-patterns.md",
        "references/runtime-rules.md",
    ],
    "frontend-testing": [
        "references/async-testing.md",
        "assets/component-test.template.tsx",
        "assets/hook-test.template.ts",
        "assets/utility-test.template.ts",
    ],
}

# Expected content patterns in template files
TEMPLATE_CONTENT_PATTERNS: dict[str, list[str]] = {
    "assets/component-test.template.tsx": [
        "@testing-library/react",
        "@testing-library/user-event",
        "describe(",
        "beforeEach(",
        "jest.clearAllMocks",
        "renderComponent",
        "it(",
    ],
    "assets/hook-test.template.ts": [
        "@testing-library/react",
        "renderHook",
        "act",
        "waitFor",
        "describe(",
        "beforeEach(",
        "jest.clearAllMocks",
        "it(",
    ],
    "assets/utility-test.template.ts": [
        "describe(",
        "it(",
        "edge cases",
        "error cases",
        "normal cases",
    ],
}

# Required H1 heading patterns for reference rule catalog files
RULE_CATALOG_FILES = {
    "backend-code-review": [
        "references/architecture-rule.md",
        "references/db-schema-rule.md",
        "references/repositories-rule.md",
        "references/sqlalchemy-rule.md",
    ],
    "frontend-code-review": [
        "references/business-logic.md",
        "references/code-quality.md",
        "references/performance.md",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML-style frontmatter from a markdown file.

    Returns a dict of key-value pairs, or empty dict if no frontmatter found.
    """
    if not content.startswith("---"):
        return {}

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}

    frontmatter_block = content[3:end_idx].strip()
    result: dict[str, str] = {}
    for line in frontmatter_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def get_h2_sections(content: str) -> list[str]:
    """Extract all H2-level headings from markdown content."""
    return re.findall(r"^## .+", content, re.MULTILINE)


def get_h1_sections(content: str) -> list[str]:
    """Extract all H1-level headings from markdown content."""
    return re.findall(r"^# .+", content, re.MULTILINE)


def has_code_blocks(content: str) -> bool:
    """Return True if the markdown contains at least one fenced code block."""
    return bool(re.search(r"```", content))


# ---------------------------------------------------------------------------
# Tests: Skills directory structure
# ---------------------------------------------------------------------------


class TestSkillsDirectoryStructure:
    """Validate the top-level .agents/skills/ directory structure."""

    def test_skills_directory_exists(self):
        """The .agents/skills/ directory must exist."""
        assert SKILLS_DIR.is_dir(), f"Expected skills directory at {SKILLS_DIR}"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_directory_exists(self, skill_name: str):
        """Each expected skill directory must exist."""
        skill_dir = SKILLS_DIR / skill_name
        assert skill_dir.is_dir(), f"Expected skill directory: {skill_dir}"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_skill_md(self, skill_name: str):
        """Every skill directory must contain a SKILL.md file."""
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"Missing SKILL.md in skill '{skill_name}'"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_not_empty(self, skill_name: str):
        """SKILL.md files must not be empty."""
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, f"SKILL.md in '{skill_name}' is empty"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_reference_files_exist(self, skill_name: str):
        """All expected reference/asset files must exist for each skill."""
        for rel_path in SKILL_REFERENCE_FILES.get(skill_name, []):
            full_path = SKILLS_DIR / skill_name / rel_path
            assert full_path.is_file(), (
                f"Missing file '{rel_path}' in skill '{skill_name}'"
            )


# ---------------------------------------------------------------------------
# Tests: SKILL.md frontmatter
# ---------------------------------------------------------------------------


class TestSkillFrontmatter:
    """Validate YAML frontmatter in SKILL.md files that use it.

    Note: frontend-testing/SKILL.md intentionally uses plain markdown without
    YAML frontmatter; it starts directly with an H1 heading. All other SKILL.md
    files use frontmatter for machine-readable metadata.
    """

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_exists(self, skill_name: str):
        """SKILL.md files that use frontmatter must start with '---'."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---"), (
            f"SKILL.md in '{skill_name}' does not start with '---' frontmatter block"
        )

    def test_frontend_testing_has_no_frontmatter_but_has_h1(self):
        """frontend-testing SKILL.md uses plain markdown (no frontmatter) and must start with H1."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        assert not content.startswith("---"), (
            "frontend-testing SKILL.md unexpectedly has frontmatter"
        )
        first_heading_match = re.search(r"^# .+", content, re.MULTILINE)
        assert first_heading_match is not None, (
            "frontend-testing SKILL.md (no frontmatter) must start with an H1 heading"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_closed(self, skill_name: str):
        """SKILL.md frontmatter block must be properly closed with '---'."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert content.count("---") >= 2, (
            f"SKILL.md in '{skill_name}' has an unclosed frontmatter block"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    @pytest.mark.parametrize("key", SKILL_REQUIRED_FRONTMATTER_KEYS)
    def test_frontmatter_required_key(self, skill_name: str, key: str):
        """SKILL.md frontmatter must contain required key."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        assert key in fm, (
            f"SKILL.md in '{skill_name}' is missing frontmatter key '{key}'"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_name_not_empty(self, skill_name: str):
        """The 'name' field in SKILL.md frontmatter must not be empty."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        assert fm.get("name", "").strip() != "", (
            f"SKILL.md in '{skill_name}' has an empty 'name' field"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_description_not_empty(self, skill_name: str):
        """The 'description' field in SKILL.md frontmatter must not be empty."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        assert fm.get("description", "").strip() != "", (
            f"SKILL.md in '{skill_name}' has an empty 'description' field"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_name_matches_directory(self, skill_name: str):
        """The 'name' in frontmatter must match the skill directory name."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        assert fm.get("name", "") == skill_name, (
            f"SKILL.md in '{skill_name}': frontmatter 'name' is '{fm.get('name')}', "
            f"expected '{skill_name}'"
        )

    @pytest.mark.parametrize("skill_name", SKILLS_WITH_FRONTMATTER)
    def test_frontmatter_description_is_meaningful(self, skill_name: str):
        """The 'description' field must be more than a few characters (not a stub)."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        desc = fm.get("description", "")
        assert len(desc) >= 20, (
            f"SKILL.md in '{skill_name}' has a very short description ({len(desc)} chars)"
        )


# ---------------------------------------------------------------------------
# Tests: SKILL.md required sections
# ---------------------------------------------------------------------------


class TestSkillSections:
    """Validate required H2 sections in every SKILL.md."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_when_to_use_section(self, skill_name: str):
        """Every SKILL.md must contain its skill-specific 'when to use/apply' heading."""
        heading = SKILL_WHEN_TO_USE_HEADINGS[skill_name]
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert heading in content, (
            f"SKILL.md in '{skill_name}' is missing expected entry-point section '{heading}'"
        )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_specific_sections_exist(self, skill_name: str):
        """Each SKILL.md must contain its skill-specific required sections."""
        specific_sections = SKILL_SPECIFIC_SECTIONS.get(skill_name, [])
        if not specific_sections:
            pytest.skip(f"No specific sections defined for '{skill_name}'")
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for section in specific_sections:
            assert section in content, (
                f"SKILL.md in '{skill_name}' is missing skill-specific section '{section}'"
            )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_has_h1_title(self, skill_name: str):
        """Every SKILL.md must have at least one H1 heading as a title."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        h1_headings = get_h1_sections(content)
        assert len(h1_headings) >= 1, (
            f"SKILL.md in '{skill_name}' has no H1-level heading"
        )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_has_multiple_sections(self, skill_name: str):
        """Every SKILL.md must have at least 2 H2 sections (not just a stub)."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        h2_sections = get_h2_sections(content)
        assert len(h2_sections) >= 2, (
            f"SKILL.md in '{skill_name}' has only {len(h2_sections)} H2 section(s), expected >= 2"
        )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_when_to_use_section_has_content(self, skill_name: str):
        """The 'when to use/apply' section must have non-empty body content."""
        heading = SKILL_WHEN_TO_USE_HEADINGS[skill_name]
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        section_idx = content.find(heading)
        assert section_idx != -1, (
            f"SKILL.md in '{skill_name}' missing expected entry-point section '{heading}'"
        )
        # Content between this heading and the next H2 heading (## ) should have actual text.
        # Use "\n## " (with trailing space) to distinguish H2 from H3 (###).
        after_section = content[section_idx + len(heading):]
        next_h2_idx = after_section.find("\n## ")
        section_body = after_section[:next_h2_idx] if next_h2_idx != -1 else after_section
        assert len(section_body.strip()) > 0, (
            f"SKILL.md in '{skill_name}': '{heading}' section has no content"
        )


# ---------------------------------------------------------------------------
# Tests: Reference files structure
# ---------------------------------------------------------------------------


class TestReferenceFilesStructure:
    """Validate that reference markdown files have proper structure."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_all_reference_files_not_empty(self, skill_name: str):
        """All reference files for a skill must not be empty."""
        for rel_path in SKILL_REFERENCE_FILES.get(skill_name, []):
            full_path = SKILLS_DIR / skill_name / rel_path
            if not full_path.is_file():
                pytest.skip(f"File does not exist: {full_path}")
            content = full_path.read_text(encoding="utf-8")
            assert len(content.strip()) > 0, (
                f"Reference file '{rel_path}' in skill '{skill_name}' is empty"
            )

    @pytest.mark.parametrize("skill_name", list(RULE_CATALOG_FILES.keys()))
    def test_rule_catalog_files_have_h1_heading(self, skill_name: str):
        """Rule catalog reference files must have an H1 heading."""
        for rel_path in RULE_CATALOG_FILES[skill_name]:
            full_path = SKILLS_DIR / skill_name / rel_path
            if not full_path.is_file():
                pytest.skip(f"File does not exist: {full_path}")
            content = full_path.read_text(encoding="utf-8")
            h1s = get_h1_sections(content)
            assert len(h1s) >= 1, (
                f"Rule catalog file '{rel_path}' in '{skill_name}' has no H1 heading"
            )

    @pytest.mark.parametrize("skill_name", list(RULE_CATALOG_FILES.keys()))
    def test_rule_catalog_files_have_rules_section(self, skill_name: str):
        """Rule catalog reference files must contain a '## Rules', '## Scope', or rule-named H2s."""
        for rel_path in RULE_CATALOG_FILES[skill_name]:
            full_path = SKILLS_DIR / skill_name / rel_path
            if not full_path.is_file():
                pytest.skip(f"File does not exist: {full_path}")
            content = full_path.read_text(encoding="utf-8")
            has_rules_section = "## Rules" in content or "## Rule" in content
            # backend-code-review references use "## Scope" + "## Rules"
            has_scope = "## Scope" in content
            # frontend-code-review references use individual rule names as H2 headings
            # (e.g., "## Use `cn()` for conditional class names") — at least 3 named rules
            h2_count = len(get_h2_sections(content))
            has_named_rules = h2_count >= 3
            assert has_rules_section or has_scope or has_named_rules, (
                f"Rule catalog file '{rel_path}' in '{skill_name}' has no '## Rules', '## Scope', "
                f"or named rule H2 headings (found {h2_count} H2 section(s))"
            )

    @pytest.mark.parametrize("skill_name", list(RULE_CATALOG_FILES.keys()))
    def test_rule_catalog_files_have_code_examples(self, skill_name: str):
        """Rule catalog reference files must contain at least one code example."""
        for rel_path in RULE_CATALOG_FILES[skill_name]:
            full_path = SKILLS_DIR / skill_name / rel_path
            if not full_path.is_file():
                pytest.skip(f"File does not exist: {full_path}")
            content = full_path.read_text(encoding="utf-8")
            assert has_code_blocks(content), (
                f"Rule catalog file '{rel_path}' in '{skill_name}' has no code examples (``` blocks)"
            )

    @pytest.mark.parametrize(
        "rel_path",
        SKILL_REFERENCE_FILES["e2e-testing"],
    )
    def test_e2e_testing_reference_files_have_h1(self, rel_path: str):
        """E2E testing reference files must have an H1 heading."""
        full_path = SKILLS_DIR / "e2e-testing" / rel_path
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        h1s = get_h1_sections(content)
        assert len(h1s) >= 1, (
            f"E2E testing reference file '{rel_path}' has no H1 heading"
        )

    @pytest.mark.parametrize(
        "rel_path",
        SKILL_REFERENCE_FILES["frontend-query-mutation"],
    )
    def test_frontend_query_reference_files_have_h1(self, rel_path: str):
        """Frontend query/mutation reference files must have an H1 heading."""
        full_path = SKILLS_DIR / "frontend-query-mutation" / rel_path
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        h1s = get_h1_sections(content)
        assert len(h1s) >= 1, (
            f"Frontend query reference file '{rel_path}' has no H1 heading"
        )

    @pytest.mark.parametrize(
        "rel_path",
        SKILL_REFERENCE_FILES["component-refactoring"],
    )
    def test_component_refactoring_reference_files_have_content(self, rel_path: str):
        """Component refactoring reference files must have substantial content."""
        full_path = SKILLS_DIR / "component-refactoring" / rel_path
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        # Must have H1 title
        h1s = get_h1_sections(content)
        assert len(h1s) >= 1, f"Component refactoring file '{rel_path}' has no H1 heading"
        # Must have code blocks showing patterns
        assert has_code_blocks(content), (
            f"Component refactoring file '{rel_path}' has no code examples"
        )

    def test_frontend_testing_async_reference_has_h1(self):
        """Frontend testing async reference file must have an H1 heading."""
        full_path = SKILLS_DIR / "frontend-testing" / "references" / "async-testing.md"
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        h1s = get_h1_sections(content)
        assert len(h1s) >= 1, "async-testing.md has no H1 heading"

    def test_frontend_testing_async_reference_has_code_blocks(self):
        """Frontend testing async reference file must have code examples."""
        full_path = SKILLS_DIR / "frontend-testing" / "references" / "async-testing.md"
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        assert has_code_blocks(content), "async-testing.md has no code examples"


# ---------------------------------------------------------------------------
# Tests: Template files content
# ---------------------------------------------------------------------------


class TestTemplateFilesContent:
    """Validate the content and patterns within TypeScript template files."""

    @pytest.mark.parametrize(
        "rel_path,expected_patterns",
        [
            (rel_path, patterns)
            for rel_path, patterns in TEMPLATE_CONTENT_PATTERNS.items()
        ],
    )
    def test_template_file_contains_expected_patterns(
        self, rel_path: str, expected_patterns: list[str]
    ):
        """Each template file must contain all its expected content patterns."""
        full_path = SKILLS_DIR / "frontend-testing" / rel_path
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        for pattern in expected_patterns:
            assert pattern in content, (
                f"Template '{rel_path}' is missing expected pattern: '{pattern}'"
            )

    def test_component_template_has_usage_comment(self):
        """Component test template must have usage instructions at the top."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx"
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        # First 20 lines must mention usage
        first_20_lines = "\n".join(content.splitlines()[:20])
        assert "Usage" in first_20_lines or "usage" in first_20_lines, (
            "component-test.template.tsx does not have usage instructions in the first 20 lines"
        )

    def test_hook_template_has_usage_comment(self):
        """Hook test template must have usage instructions at the top."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts"
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        first_20_lines = "\n".join(content.splitlines()[:20])
        assert "Usage" in first_20_lines or "usage" in first_20_lines, (
            "hook-test.template.ts does not have usage instructions in the first 20 lines"
        )

    def test_utility_template_has_usage_comment(self):
        """Utility test template must have usage instructions at the top."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "utility-test.template.ts"
        if not full_path.is_file():
            pytest.skip(f"File does not exist: {full_path}")
        content = full_path.read_text(encoding="utf-8")
        first_20_lines = "\n".join(content.splitlines()[:20])
        assert "Usage" in first_20_lines or "usage" in first_20_lines, (
            "utility-test.template.ts does not have usage instructions in the first 20 lines"
        )

    def test_component_template_imports_testing_library(self):
        """Component template must import from @testing-library/react."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx"
        content = full_path.read_text(encoding="utf-8")
        assert "@testing-library/react" in content, (
            "component-test.template.tsx does not import from @testing-library/react"
        )

    def test_hook_template_uses_render_hook(self):
        """Hook template must use renderHook from @testing-library/react."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts"
        content = full_path.read_text(encoding="utf-8")
        assert "renderHook" in content, "hook-test.template.ts does not use renderHook"

    def test_hook_template_imports_from_testing_library(self):
        """Hook template must import renderHook, act, and waitFor."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts"
        content = full_path.read_text(encoding="utf-8")
        for symbol in ["renderHook", "act", "waitFor"]:
            assert symbol in content, (
                f"hook-test.template.ts does not import '{symbol}'"
            )

    def test_component_template_clears_mocks_in_before_each(self):
        """Component template must clear mocks in beforeEach to prevent test pollution."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx"
        content = full_path.read_text(encoding="utf-8")
        assert "jest.clearAllMocks" in content, (
            "component-test.template.tsx does not call jest.clearAllMocks in beforeEach"
        )

    def test_hook_template_clears_mocks_in_before_each(self):
        """Hook template must clear mocks in beforeEach to prevent test pollution."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts"
        content = full_path.read_text(encoding="utf-8")
        assert "jest.clearAllMocks" in content, (
            "hook-test.template.ts does not call jest.clearAllMocks in beforeEach"
        )

    def test_component_template_does_not_use_vitest_apis(self):
        """Component template must not use Vitest APIs (project uses Jest)."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx"
        content = full_path.read_text(encoding="utf-8")
        vitest_imports = ["from 'vitest'", 'from "vitest"', "import { vi }", "vi.fn()"]
        for vi_pattern in vitest_imports:
            assert vi_pattern not in content, (
                f"component-test.template.tsx uses Vitest API '{vi_pattern}' — project uses Jest"
            )

    def test_hook_template_does_not_use_vitest_apis(self):
        """Hook template must not use Vitest APIs (project uses Jest)."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts"
        content = full_path.read_text(encoding="utf-8")
        assert 'from "vitest"' not in content and "from 'vitest'" not in content, (
            "hook-test.template.ts uses Vitest API — project uses Jest"
        )

    def test_component_template_has_edge_cases_section(self):
        """Component template must have an edge cases section for adversarial testing."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx"
        content = full_path.read_text(encoding="utf-8")
        assert "edge cases" in content.lower(), (
            "component-test.template.tsx lacks an 'edge cases' section"
        )

    def test_utility_template_has_error_cases_section(self):
        """Utility template must have an error cases section."""
        full_path = SKILLS_DIR / "frontend-testing" / "assets" / "utility-test.template.ts"
        content = full_path.read_text(encoding="utf-8")
        assert "error cases" in content.lower(), (
            "utility-test.template.ts lacks an 'error cases' section"
        )


# ---------------------------------------------------------------------------
# Tests: Cross-references from SKILL.md
# ---------------------------------------------------------------------------


class TestSkillCrossReferences:
    """Validate that internal cross-references in SKILL.md files resolve to existing files."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_references_resolve(self, skill_name: str):
        """All [text](path) links in SKILL.md that point to local files must exist."""
        skill_dir = SKILLS_DIR / skill_name
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        # Find all markdown links: [text](path)
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        for link_text, link_target in links:
            # Skip external URLs and anchors
            if link_target.startswith("http") or link_target.startswith("#"):
                continue
            # Local file reference
            resolved = (skill_dir / link_target).resolve()
            assert resolved.is_file(), (
                f"SKILL.md in '{skill_name}': link '[{link_text}]({link_target})' "
                f"resolves to non-existent file: {resolved}"
            )

    @pytest.mark.parametrize("skill_name", list(RULE_CATALOG_FILES.keys()))
    def test_rule_catalog_references_resolve(self, skill_name: str):
        """All local file links in rule catalog files must resolve."""
        for rel_path in RULE_CATALOG_FILES[skill_name]:
            ref_file = SKILLS_DIR / skill_name / rel_path
            if not ref_file.is_file():
                continue
            content = ref_file.read_text(encoding="utf-8")
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            for link_text, link_target in links:
                if link_target.startswith("http") or link_target.startswith("#"):
                    continue
                resolved = (ref_file.parent / link_target).resolve()
                assert resolved.is_file(), (
                    f"Rule catalog '{rel_path}' in '{skill_name}': "
                    f"link '[{link_text}]({link_target})' resolves to non-existent file: {resolved}"
                )


# ---------------------------------------------------------------------------
# Tests: Specific skill content checks
# ---------------------------------------------------------------------------


class TestBackendCodeReviewSkill:
    """Validate specific content of the backend-code-review skill."""

    def test_skill_md_contains_severity_levels(self):
        """backend-code-review SKILL.md must define severity levels."""
        content = (SKILLS_DIR / "backend-code-review" / "SKILL.md").read_text(encoding="utf-8")
        assert "critical" in content.lower() or "Critical" in content, (
            "backend-code-review SKILL.md does not mention severity level 'critical'"
        )

    def test_skill_md_has_template_a_and_b(self):
        """backend-code-review SKILL.md must define Template A and Template B output formats."""
        content = (SKILLS_DIR / "backend-code-review" / "SKILL.md").read_text(encoding="utf-8")
        assert "Template A" in content, "backend-code-review SKILL.md missing 'Template A'"
        assert "Template B" in content, "backend-code-review SKILL.md missing 'Template B'"

    def test_architecture_rule_has_scope_section(self):
        """architecture-rule.md must have a ## Scope section."""
        content = (
            SKILLS_DIR / "backend-code-review" / "references" / "architecture-rule.md"
        ).read_text(encoding="utf-8")
        assert "## Scope" in content, "architecture-rule.md is missing '## Scope' section"

    def test_db_schema_rule_has_scope_section(self):
        """db-schema-rule.md must have a ## Scope section."""
        content = (
            SKILLS_DIR / "backend-code-review" / "references" / "db-schema-rule.md"
        ).read_text(encoding="utf-8")
        assert "## Scope" in content, "db-schema-rule.md is missing '## Scope' section"

    def test_sqlalchemy_rule_has_scope_section(self):
        """sqlalchemy-rule.md must have a ## Scope section."""
        content = (
            SKILLS_DIR / "backend-code-review" / "references" / "sqlalchemy-rule.md"
        ).read_text(encoding="utf-8")
        assert "## Scope" in content, "sqlalchemy-rule.md is missing '## Scope' section"

    def test_repositories_rule_has_scope_section(self):
        """repositories-rule.md must have a ## Scope section."""
        content = (
            SKILLS_DIR / "backend-code-review" / "references" / "repositories-rule.md"
        ).read_text(encoding="utf-8")
        assert "## Scope" in content, "repositories-rule.md is missing '## Scope' section"

    def test_skill_md_references_all_rule_files(self):
        """backend-code-review SKILL.md must reference all its rule catalog files."""
        content = (SKILLS_DIR / "backend-code-review" / "SKILL.md").read_text(encoding="utf-8")
        for ref_file in RULE_CATALOG_FILES["backend-code-review"]:
            # Extract the filename to check it appears in the SKILL.md
            filename = Path(ref_file).name
            assert filename in content, (
                f"backend-code-review SKILL.md does not reference rule file '{filename}'"
            )

    def test_sqlalchemy_rule_has_user_id_scoping_rule(self):
        """sqlalchemy-rule.md must document the user_id scoping requirement for security."""
        content = (
            SKILLS_DIR / "backend-code-review" / "references" / "sqlalchemy-rule.md"
        ).read_text(encoding="utf-8")
        assert "user_id" in content, (
            "sqlalchemy-rule.md does not document user_id scoping (security requirement)"
        )


class TestComponentRefactoringSkill:
    """Validate specific content of the component-refactoring skill."""

    def test_skill_md_has_complexity_threshold(self):
        """component-refactoring SKILL.md must define a complexity threshold."""
        content = (SKILLS_DIR / "component-refactoring" / "SKILL.md").read_text(encoding="utf-8")
        assert "Complexity Threshold" in content or "complexity" in content.lower(), (
            "component-refactoring SKILL.md does not mention complexity threshold"
        )

    def test_skill_md_mentions_lint_and_type_check(self):
        """component-refactoring SKILL.md must mention lint and type-check commands."""
        content = (SKILLS_DIR / "component-refactoring" / "SKILL.md").read_text(encoding="utf-8")
        assert "lint" in content, "component-refactoring SKILL.md does not mention 'lint'"
        assert "type-check" in content, "component-refactoring SKILL.md does not mention 'type-check'"

    def test_complexity_patterns_has_before_after_examples(self):
        """complexity-patterns.md must contain Before/After code examples."""
        content = (
            SKILLS_DIR / "component-refactoring" / "references" / "complexity-patterns.md"
        ).read_text(encoding="utf-8")
        assert "Before" in content or "before" in content.lower(), (
            "complexity-patterns.md has no 'Before' examples"
        )
        assert "After" in content or "after" in content.lower(), (
            "complexity-patterns.md has no 'After' examples"
        )

    def test_component_splitting_mentions_kebab_case(self):
        """component-splitting.md must document the kebab-case naming convention."""
        content = (
            SKILLS_DIR / "component-refactoring" / "references" / "component-splitting.md"
        ).read_text(encoding="utf-8")
        assert "kebab-case" in content, (
            "component-splitting.md does not mention kebab-case naming convention"
        )

    def test_hook_extraction_has_naming_conventions(self):
        """hook-extraction.md must have a naming conventions section."""
        content = (
            SKILLS_DIR / "component-refactoring" / "references" / "hook-extraction.md"
        ).read_text(encoding="utf-8")
        assert "Naming" in content or "naming" in content.lower(), (
            "hook-extraction.md does not document naming conventions"
        )


class TestE2ETestingSkill:
    """Validate specific content of the e2e-testing skill."""

    def test_skill_md_mentions_playwright(self):
        """e2e-testing SKILL.md must mention Playwright."""
        content = (SKILLS_DIR / "e2e-testing" / "SKILL.md").read_text(encoding="utf-8")
        assert "Playwright" in content or "playwright" in content, (
            "e2e-testing SKILL.md does not mention Playwright"
        )

    def test_fixtures_md_documents_import_rule(self):
        """fixtures.md must document the import rule (always use ../../fixtures)."""
        content = (
            SKILLS_DIR / "e2e-testing" / "references" / "fixtures.md"
        ).read_text(encoding="utf-8")
        assert "../../fixtures" in content or "fixtures" in content, (
            "e2e-testing fixtures.md does not document the import rule"
        )

    def test_selectors_md_documents_data_testid(self):
        """selectors.md must document the data-testid selector pattern."""
        content = (
            SKILLS_DIR / "e2e-testing" / "references" / "selectors.md"
        ).read_text(encoding="utf-8")
        assert "data-testid" in content or "testid" in content.lower(), (
            "e2e-testing selectors.md does not document data-testid selectors"
        )

    def test_helpers_md_documents_await_bootstrap_test(self):
        """helpers.md must document the awaitBootstrapTest helper function."""
        content = (
            SKILLS_DIR / "e2e-testing" / "references" / "helpers.md"
        ).read_text(encoding="utf-8")
        assert "awaitBootstrapTest" in content, (
            "e2e-testing helpers.md does not document awaitBootstrapTest"
        )


class TestFrontendCodeReviewSkill:
    """Validate specific content of the frontend-code-review skill."""

    def test_skill_md_mentions_tech_stack(self):
        """frontend-code-review SKILL.md must mention the tech stack."""
        content = (SKILLS_DIR / "frontend-code-review" / "SKILL.md").read_text(encoding="utf-8")
        # The skill should mention the key frontend technologies
        tech_terms = ["React", "TypeScript", "Tailwind", "Zustand"]
        mentioned = [t for t in tech_terms if t in content]
        assert len(mentioned) >= 2, (
            f"frontend-code-review SKILL.md mentions only {mentioned} of {tech_terms}"
        )

    def test_code_quality_md_has_rules(self):
        """code-quality.md must have multiple H3 rule entries."""
        content = (
            SKILLS_DIR / "frontend-code-review" / "references" / "code-quality.md"
        ).read_text(encoding="utf-8")
        h3_rules = re.findall(r"^### .+", content, re.MULTILINE)
        assert len(h3_rules) >= 3, (
            f"code-quality.md has only {len(h3_rules)} H3 rule entries, expected >= 3"
        )

    def test_performance_md_has_rules(self):
        """performance.md must have multiple H3 rule entries."""
        content = (
            SKILLS_DIR / "frontend-code-review" / "references" / "performance.md"
        ).read_text(encoding="utf-8")
        h3_rules = re.findall(r"^### .+", content, re.MULTILINE)
        assert len(h3_rules) >= 2, (
            f"performance.md has only {len(h3_rules)} H3 rule entries, expected >= 2"
        )

    def test_business_logic_md_has_rules(self):
        """business-logic.md must have multiple rule entries."""
        content = (
            SKILLS_DIR / "frontend-code-review" / "references" / "business-logic.md"
        ).read_text(encoding="utf-8")
        h3_rules = re.findall(r"^### .+", content, re.MULTILINE)
        assert len(h3_rules) >= 2, (
            f"business-logic.md has only {len(h3_rules)} H3 rule entries, expected >= 2"
        )

    def test_skill_md_has_template_a_and_b(self):
        """frontend-code-review SKILL.md must define Template A and B output formats."""
        content = (SKILLS_DIR / "frontend-code-review" / "SKILL.md").read_text(encoding="utf-8")
        assert "Template A" in content, "frontend-code-review SKILL.md missing 'Template A'"
        assert "Template B" in content, "frontend-code-review SKILL.md missing 'Template B'"


class TestFrontendQueryMutationSkill:
    """Validate specific content of the frontend-query-mutation skill."""

    def test_skill_md_mentions_use_request_processor(self):
        """frontend-query-mutation SKILL.md must mention UseRequestProcessor."""
        content = (SKILLS_DIR / "frontend-query-mutation" / "SKILL.md").read_text(encoding="utf-8")
        assert "UseRequestProcessor" in content, (
            "frontend-query-mutation SKILL.md does not mention UseRequestProcessor"
        )

    def test_query_patterns_md_has_code_examples(self):
        """query-patterns.md must contain code examples for hooks."""
        content = (
            SKILLS_DIR / "frontend-query-mutation" / "references" / "query-patterns.md"
        ).read_text(encoding="utf-8")
        assert has_code_blocks(content), "query-patterns.md has no code examples"

    def test_runtime_rules_md_has_code_examples(self):
        """runtime-rules.md must contain code examples."""
        content = (
            SKILLS_DIR / "frontend-query-mutation" / "references" / "runtime-rules.md"
        ).read_text(encoding="utf-8")
        assert has_code_blocks(content), "runtime-rules.md has no code examples"

    def test_query_patterns_md_mentions_anti_patterns(self):
        """query-patterns.md must document anti-patterns to avoid."""
        content = (
            SKILLS_DIR / "frontend-query-mutation" / "references" / "query-patterns.md"
        ).read_text(encoding="utf-8")
        assert "Anti-Pattern" in content or "anti-pattern" in content.lower(), (
            "query-patterns.md does not document anti-patterns"
        )


class TestFrontendTestingSkill:
    """Validate specific content of the frontend-testing skill."""

    def test_skill_md_mentions_jest(self):
        """frontend-testing SKILL.md must mention Jest."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        assert "Jest" in content or "jest" in content, (
            "frontend-testing SKILL.md does not mention Jest"
        )

    def test_skill_md_mentions_react_testing_library(self):
        """frontend-testing SKILL.md must mention React Testing Library."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        assert "Testing Library" in content or "testing-library" in content, (
            "frontend-testing SKILL.md does not mention React Testing Library"
        )

    def test_skill_md_forbids_vitest(self):
        """frontend-testing SKILL.md must explicitly forbid or warn against Vitest APIs."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        # The skill should mention Vitest in a "do not use" context
        assert "Vitest" in content or "vitest" in content, (
            "frontend-testing SKILL.md should address Vitest (to forbid its use)"
        )

    def test_skill_md_mentions_challenge_tests(self):
        """frontend-testing SKILL.md must mention challenge/adversarial tests."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        assert "challenge" in content.lower() or "adversarial" in content.lower(), (
            "frontend-testing SKILL.md does not mention challenge/adversarial tests"
        )

    def test_async_testing_md_covers_wait_for(self):
        """async-testing.md must cover the waitFor pattern."""
        content = (
            SKILLS_DIR / "frontend-testing" / "references" / "async-testing.md"
        ).read_text(encoding="utf-8")
        assert "waitFor" in content, "async-testing.md does not document waitFor"

    def test_async_testing_md_covers_fake_timers(self):
        """async-testing.md must cover fake timer patterns."""
        content = (
            SKILLS_DIR / "frontend-testing" / "references" / "async-testing.md"
        ).read_text(encoding="utf-8")
        assert "Fake Timer" in content or "useFakeTimers" in content, (
            "async-testing.md does not document fake timer usage"
        )

    def test_skill_md_documents_anti_patterns(self):
        """frontend-testing SKILL.md must document anti-patterns."""
        content = (SKILLS_DIR / "frontend-testing" / "SKILL.md").read_text(encoding="utf-8")
        # The Liar, The Mirror, etc. are documented anti-patterns
        assert "Anti-Pattern" in content or "anti-pattern" in content.lower() or "Liar" in content, (
            "frontend-testing SKILL.md does not document testing anti-patterns"
        )


# ---------------------------------------------------------------------------
# Tests: Boundary / regression checks
# ---------------------------------------------------------------------------


class TestBoundaryAndRegressionCases:
    """Edge case and regression tests for skill file validation."""

    def test_no_skill_directory_without_skill_md(self):
        """Every subdirectory under .agents/skills/ must have a SKILL.md."""
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.is_file(), (
                f"Skill directory '{skill_dir.name}' has no SKILL.md"
            )

    def test_skill_md_does_not_contain_placeholder_text(self):
        """SKILL.md files must not contain obvious placeholder text (TODO, FIXME, PLACEHOLDER)."""
        placeholder_patterns = ["TODO:", "FIXME:", "PLACEHOLDER", "<FILL_IN>"]
        for skill_name in EXPECTED_SKILLS:
            content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for placeholder in placeholder_patterns:
                assert placeholder not in content, (
                    f"SKILL.md in '{skill_name}' contains placeholder text: '{placeholder}'"
                )

    def test_template_files_contain_template_placeholders(self):
        """Template files must contain TEMPLATE_ placeholders to signal they need customization."""
        template_files = [
            SKILLS_DIR / "frontend-testing" / "assets" / "component-test.template.tsx",
            SKILLS_DIR / "frontend-testing" / "assets" / "hook-test.template.ts",
            SKILLS_DIR / "frontend-testing" / "assets" / "utility-test.template.ts",
        ]
        for template_file in template_files:
            if not template_file.is_file():
                continue
            content = template_file.read_text(encoding="utf-8")
            assert "TEMPLATE_" in content, (
                f"Template file '{template_file.name}' has no TEMPLATE_ placeholders — "
                "users need these to know what to replace"
            )

    def test_all_skill_files_are_utf8_encoded(self):
        """All .md, .tsx, and .ts files in .agents/skills/ must be valid UTF-8."""
        for skill_name in EXPECTED_SKILLS:
            skill_dir = SKILLS_DIR / skill_name
            for file_path in skill_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix not in {".md", ".ts", ".tsx"}:
                    continue
                try:
                    file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError as exc:
                    pytest.fail(
                        f"File '{file_path.relative_to(SKILLS_DIR)}' is not valid UTF-8: {exc}"
                    )

    def test_skill_frontmatter_name_uses_kebab_case(self):
        """SKILL.md 'name' field must use kebab-case (lowercase with hyphens)."""
        kebab_pattern = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
        for skill_name in SKILLS_WITH_FRONTMATTER:
            content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            name = fm.get("name", "")
            assert kebab_pattern.match(name), (
                f"SKILL.md in '{skill_name}': name '{name}' is not valid kebab-case"
            )

    def test_reference_files_have_h2_sections(self):
        """All reference .md files (not templates) must have at least one H2 section."""
        for skill_name in EXPECTED_SKILLS:
            for rel_path in SKILL_REFERENCE_FILES.get(skill_name, []):
                # Skip template/asset files (not reference docs)
                if not rel_path.startswith("references/"):
                    continue
                full_path = SKILLS_DIR / skill_name / rel_path
                if not full_path.is_file():
                    continue
                content = full_path.read_text(encoding="utf-8")
                h2s = get_h2_sections(content)
                assert len(h2s) >= 1, (
                    f"Reference file '{rel_path}' in '{skill_name}' has no H2 section headings"
                )

    def test_skill_total_file_count_per_skill(self):
        """Each skill directory must have at least 2 files (SKILL.md + at least 1 reference)."""
        for skill_name in EXPECTED_SKILLS:
            skill_dir = SKILLS_DIR / skill_name
            all_files = [f for f in skill_dir.rglob("*") if f.is_file()]
            assert len(all_files) >= 2, (
                f"Skill '{skill_name}' has only {len(all_files)} file(s); expected SKILL.md + references"
            )

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_line_count_is_substantial(self, skill_name: str):
        """SKILL.md files must be at least 50 lines (not stubs)."""
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        assert line_count >= 50, (
            f"SKILL.md in '{skill_name}' has only {line_count} lines — likely a stub"
        )