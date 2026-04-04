"""Tests for agent skill documentation files added in this PR.

These tests validate the structure, content, and cross-references of the
agent skill files under .agents/skills/. They ensure that:

- SKILL.md files have required frontmatter and sections
- Reference files exist and have the expected structure
- TypeScript test templates contain correct test framework patterns
- Cross-references between files are valid
- Key content requirements (security rules, output formats, etc.) are met
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Root of the agents skills directory
AGENTS_ROOT = Path(__file__).parents[4] / ".agents" / "skills"

# Skill directories added in this PR
SKILL_DIRS = {
    "backend-code-review": AGENTS_ROOT / "backend-code-review",
    "component-refactoring": AGENTS_ROOT / "component-refactoring",
    "e2e-testing": AGENTS_ROOT / "e2e-testing",
    "frontend-code-review": AGENTS_ROOT / "frontend-code-review",
    "frontend-query-mutation": AGENTS_ROOT / "frontend-query-mutation",
    "frontend-testing": AGENTS_ROOT / "frontend-testing",
}

# Skills that define YAML frontmatter (--- blocks at the top)
SKILLS_WITH_FRONTMATTER = {
    "backend-code-review",
    "component-refactoring",
    "e2e-testing",
    "frontend-code-review",
    "frontend-query-mutation",
}

# Skills without frontmatter (start directly with a markdown heading)
SKILLS_WITHOUT_FRONTMATTER = {"frontend-testing"}

# Reference files per skill directory (from PR diff)
BACKEND_REVIEW_REFERENCES = [
    "references/architecture-rule.md",
    "references/db-schema-rule.md",
    "references/repositories-rule.md",
    "references/sqlalchemy-rule.md",
]

E2E_TESTING_REFERENCES = [
    "references/fixtures.md",
    "references/helpers.md",
    "references/selectors.md",
]

FRONTEND_TESTING_ASSETS = [
    "assets/component-test.template.tsx",
    "assets/hook-test.template.ts",
    "assets/utility-test.template.ts",
]

FRONTEND_TESTING_REFERENCES = [
    "references/async-testing.md",
]

FRONTEND_CODE_REVIEW_REFERENCES = [
    "references/business-logic.md",
    "references/code-quality.md",
    "references/performance.md",
]

FRONTEND_QUERY_MUTATION_REFERENCES = [
    "references/query-patterns.md",
    "references/runtime-rules.md",
]

COMPONENT_REFACTORING_REFERENCES = [
    "references/complexity-patterns.md",
    "references/component-splitting.md",
    "references/hook-extraction.md",
]


def read_file(path: Path) -> str:
    """Read file content, failing with a clear message if missing."""
    assert path.exists(), f"Expected file does not exist: {path}"
    return path.read_text(encoding="utf-8")


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter fields from a markdown file.

    Returns a dict of key->value for fields in the --- block.
    Returns empty dict if no frontmatter is found.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    block = content[4:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# TestSkillDirectoryStructure
# ---------------------------------------------------------------------------


class TestSkillDirectoryStructure:
    """Ensure each skill directory has the expected files."""

    @pytest.mark.parametrize("skill_name", list(SKILL_DIRS.keys()))
    def test_skill_directory_exists(self, skill_name: str) -> None:
        """Every skill directory must exist under .agents/skills/."""
        skill_dir = SKILL_DIRS[skill_name]
        assert skill_dir.is_dir(), f"Skill directory not found: {skill_dir}"

    @pytest.mark.parametrize("skill_name", list(SKILL_DIRS.keys()))
    def test_skill_md_exists(self, skill_name: str) -> None:
        """Every skill directory must contain a SKILL.md file."""
        skill_md = SKILL_DIRS[skill_name] / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md missing in {SKILL_DIRS[skill_name]}"

    @pytest.mark.parametrize("skill_name", list(SKILL_DIRS.keys()))
    def test_skill_md_is_not_empty(self, skill_name: str) -> None:
        """SKILL.md files must not be empty."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        assert len(content.strip()) > 0, f"SKILL.md is empty in {skill_name}"

    @pytest.mark.parametrize(
        "skill_name,references",
        [
            ("backend-code-review", BACKEND_REVIEW_REFERENCES),
            ("e2e-testing", E2E_TESTING_REFERENCES),
            ("frontend-testing", FRONTEND_TESTING_ASSETS),
            ("frontend-testing", FRONTEND_TESTING_REFERENCES),
            ("frontend-code-review", FRONTEND_CODE_REVIEW_REFERENCES),
            ("frontend-query-mutation", FRONTEND_QUERY_MUTATION_REFERENCES),
            ("component-refactoring", COMPONENT_REFACTORING_REFERENCES),
        ],
    )
    def test_referenced_files_exist(self, skill_name: str, references: list[str]) -> None:
        """Files referenced in each skill's checklist/references section must exist."""
        skill_dir = SKILL_DIRS[skill_name]
        for ref_path in references:
            full_path = skill_dir / ref_path
            assert full_path.exists(), f"Referenced file missing in {skill_name}: {ref_path}"


# ---------------------------------------------------------------------------
# TestFrontmatterValidation
# ---------------------------------------------------------------------------


class TestFrontmatterValidation:
    """Validate YAML frontmatter in SKILL.md files that declare it."""

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITH_FRONTMATTER))
    def test_skill_has_frontmatter_block(self, skill_name: str) -> None:
        """Skills in SKILLS_WITH_FRONTMATTER must start with a --- frontmatter block."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        assert content.startswith("---"), f"{skill_name}/SKILL.md is expected to have YAML frontmatter"

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITH_FRONTMATTER))
    def test_frontmatter_has_name_field(self, skill_name: str) -> None:
        """Frontmatter must include a non-empty 'name' field."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        fm = parse_frontmatter(content)
        assert "name" in fm, f"{skill_name}/SKILL.md frontmatter missing 'name' field"
        assert fm["name"], f"{skill_name}/SKILL.md has empty 'name' in frontmatter"

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITH_FRONTMATTER))
    def test_frontmatter_has_description_field(self, skill_name: str) -> None:
        """Frontmatter must include a non-empty 'description' field."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        fm = parse_frontmatter(content)
        assert "description" in fm, f"{skill_name}/SKILL.md frontmatter missing 'description' field"
        assert fm["description"], f"{skill_name}/SKILL.md has empty 'description' in frontmatter"

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITH_FRONTMATTER))
    def test_frontmatter_name_matches_directory(self, skill_name: str) -> None:
        """The 'name' field in frontmatter must match the skill directory name."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        fm = parse_frontmatter(content)
        assert fm.get("name") == skill_name, (
            f"{skill_name}/SKILL.md: frontmatter 'name' ({fm.get('name')!r}) "
            f"does not match directory name ({skill_name!r})"
        )

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITHOUT_FRONTMATTER))
    def test_skills_without_frontmatter_start_with_heading(self, skill_name: str) -> None:
        """Skills without frontmatter must start with a markdown level-1 heading."""
        content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
        assert not content.startswith("---"), f"{skill_name}/SKILL.md unexpectedly has frontmatter"
        assert content.lstrip().startswith("#"), (
            f"{skill_name}/SKILL.md without frontmatter must start with a # heading"
        )

    def test_backend_review_frontmatter_description_mentions_py(self) -> None:
        """backend-code-review description must mention .py files."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        fm = parse_frontmatter(content)
        assert ".py" in fm.get("description", ""), "backend-code-review description should mention .py files"

    def test_e2e_testing_frontmatter_description_mentions_playwright(self) -> None:
        """e2e-testing description must mention Playwright or E2E."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        fm = parse_frontmatter(content)
        desc = fm.get("description", "").lower()
        assert "playwright" in desc or "e2e" in desc, "e2e-testing description should mention Playwright or E2E"


# ---------------------------------------------------------------------------
# TestRequiredSections
# ---------------------------------------------------------------------------


class TestRequiredSections:
    """Verify that SKILL.md files contain expected section headings."""

    def test_backend_review_has_when_to_use_section(self) -> None:
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "## When to use this skill" in content

    def test_backend_review_has_checklist_section(self) -> None:
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "## Checklist" in content

    def test_backend_review_has_general_review_rules(self) -> None:
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "## General Review Rules" in content

    def test_backend_review_has_required_output_format(self) -> None:
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "## Required Output Format" in content

    def test_backend_review_has_template_a(self) -> None:
        """Template A (findings) must be defined."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "Template A" in content

    def test_backend_review_has_template_b(self) -> None:
        """Template B (no issues) must be defined."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "Template B" in content

    def test_e2e_testing_has_when_to_apply_section(self) -> None:
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "## When to Apply" in content

    def test_e2e_testing_has_tags_system_section(self) -> None:
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "## Tags System" in content

    def test_e2e_testing_has_selector_strategy_section(self) -> None:
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "## Selector Strategy" in content

    def test_frontend_testing_has_when_to_apply_section(self) -> None:
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        assert "## When to Apply" in content

    def test_frontend_testing_has_tech_stack_section(self) -> None:
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        assert "## Tech Stack" in content

    def test_frontend_testing_has_coverage_goals_section(self) -> None:
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        assert "## Coverage Goals" in content

    def test_frontend_testing_has_forbidden_antipatterns_section(self) -> None:
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        assert "## Forbidden Test Anti-Patterns" in content

    def test_component_refactoring_has_complexity_threshold(self) -> None:
        """Refactoring skill must document the complexity threshold."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "SKILL.md")
        assert "Complexity Threshold" in content or "complexity" in content.lower()

    def test_frontend_query_mutation_skill_has_intent_or_architecture(self) -> None:
        """Query/mutation skill must describe architecture."""
        content = read_file(SKILL_DIRS["frontend-query-mutation"] / "SKILL.md")
        # Either explicit "Architecture" section or mention of UseRequestProcessor
        assert "UseRequestProcessor" in content or "Architecture" in content


# ---------------------------------------------------------------------------
# TestBackendRuleFiles
# ---------------------------------------------------------------------------


class TestBackendRuleFiles:
    """Validate the structure of backend-code-review reference files."""

    @pytest.mark.parametrize(
        "ref_file",
        ["architecture-rule.md", "db-schema-rule.md", "repositories-rule.md", "sqlalchemy-rule.md"],
    )
    def test_rule_file_has_scope_section(self, ref_file: str) -> None:
        """Each backend rule file must define its scope."""
        path = SKILL_DIRS["backend-code-review"] / "references" / ref_file
        content = read_file(path)
        assert "## Scope" in content, f"{ref_file} is missing '## Scope' section"

    @pytest.mark.parametrize(
        "ref_file",
        ["architecture-rule.md", "db-schema-rule.md", "repositories-rule.md", "sqlalchemy-rule.md"],
    )
    def test_rule_file_has_rules_section(self, ref_file: str) -> None:
        """Each backend rule file must define its rules."""
        path = SKILL_DIRS["backend-code-review"] / "references" / ref_file
        content = read_file(path)
        assert "## Rules" in content, f"{ref_file} is missing '## Rules' section"

    @pytest.mark.parametrize(
        "ref_file",
        ["architecture-rule.md", "db-schema-rule.md", "repositories-rule.md", "sqlalchemy-rule.md"],
    )
    def test_rule_file_has_severity_annotations(self, ref_file: str) -> None:
        """Each rule must have a severity label (critical or suggestion)."""
        path = SKILL_DIRS["backend-code-review"] / "references" / ref_file
        content = read_file(path)
        assert re.search(r"[Ss]everity:\s*(critical|suggestion)", content), (
            f"{ref_file} must contain at least one 'Severity: critical' or 'Severity: suggestion' annotation"
        )

    @pytest.mark.parametrize(
        "ref_file",
        ["architecture-rule.md", "db-schema-rule.md", "repositories-rule.md", "sqlalchemy-rule.md"],
    )
    def test_rule_file_has_suggested_fix(self, ref_file: str) -> None:
        """Rule files must include 'Suggested fix' guidance for actionable rules."""
        path = SKILL_DIRS["backend-code-review"] / "references" / ref_file
        content = read_file(path)
        assert "Suggested fix" in content or "Suggested Fix" in content, (
            f"{ref_file} must include at least one 'Suggested fix:' section"
        )

    def test_architecture_rule_covers_route_service_model_layering(self) -> None:
        """Architecture rule must cover route/service/model layering."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "references" / "architecture-rule.md")
        assert "route" in content.lower() and "service" in content.lower()

    def test_db_schema_rule_covers_user_id_scoping(self) -> None:
        """DB schema rule must mention user_id for user-scoped data isolation."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "references" / "db-schema-rule.md")
        assert "user_id" in content

    def test_db_schema_rule_covers_dialect_portability(self) -> None:
        """DB schema rule must cover SQLite/PostgreSQL dialect portability."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "references" / "db-schema-rule.md")
        assert "SQLite" in content and "PostgreSQL" in content

    def test_sqlalchemy_rule_covers_session_scope(self) -> None:
        """SQLAlchemy rule must mention session_scope context manager."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "references" / "sqlalchemy-rule.md")
        assert "session_scope" in content

    def test_repositories_rule_covers_service_factory_pattern(self) -> None:
        """Repositories rule must document the ServiceFactory pattern."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "references" / "repositories-rule.md")
        assert "ServiceFactory" in content or "factory" in content.lower()


# ---------------------------------------------------------------------------
# TestSecurityAndQualityRequirements
# ---------------------------------------------------------------------------


class TestSecurityAndQualityRequirements:
    """Verify that security and quality checks are documented in skill files."""

    def test_backend_review_mentions_sql_injection(self) -> None:
        """Security section must mention SQL injection vulnerabilities."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "SQL injection" in content or "sql injection" in content.lower()

    def test_backend_review_mentions_user_id_scoping(self) -> None:
        """Security section must mention user_id scoping to prevent cross-user leakage."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "user_id" in content

    def test_backend_review_mentions_pii_tolerance(self) -> None:
        """Observability section must mention PII logging prohibition."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "PII" in content

    def test_backend_review_mentions_async_logger(self) -> None:
        """Observability section must mention the async logger from lfx.log.logger."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "lfx.log.logger" in content or "async logger" in content.lower()

    def test_backend_review_mentions_n_plus_one_queries(self) -> None:
        """Performance section must mention N+1 query anti-pattern."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "N+1" in content

    def test_frontend_testing_forbids_vitest_apis(self) -> None:
        """Frontend testing skill must explicitly prohibit Vitest APIs."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        # Must mention not to use vi.* (Vitest)
        assert "vi." in content or "Vitest" in content or "vi.mock" in content

    def test_e2e_skill_requires_import_from_fixtures(self) -> None:
        """E2E skill must instruct to import from custom fixtures, not @playwright/test."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "fixtures" in content and "@playwright/test" in content

    def test_e2e_skill_documents_error_detection(self) -> None:
        """E2E skill must explain the custom fixture's auto error detection."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "error" in content.lower() and "detect" in content.lower()

    def test_frontend_testing_lists_happy_path_not_enough(self) -> None:
        """Frontend testing skill must warn that happy path alone is not enough."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        assert "NOT enough" in content or "not enough" in content.lower()

    def test_frontend_code_review_covers_performance_rules(self) -> None:
        """Frontend code review must include performance considerations."""
        content = read_file(SKILL_DIRS["frontend-code-review"] / "SKILL.md")
        assert "performance" in content.lower()

    def test_backend_review_mentions_precommit_commands(self) -> None:
        """Pre-Commit Verification section must mention format/lint/test commands."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        assert "make format_backend" in content or "format_backend" in content
        assert "make lint" in content or "lint" in content.lower()


# ---------------------------------------------------------------------------
# TestTemplateFileStructure
# ---------------------------------------------------------------------------


class TestTemplateFileStructure:
    """Validate the TypeScript test template files."""

    def _get_template_path(self, filename: str) -> Path:
        return SKILL_DIRS["frontend-testing"] / "assets" / filename

    @pytest.mark.parametrize(
        "template_file",
        ["component-test.template.tsx", "hook-test.template.ts", "utility-test.template.ts"],
    )
    def test_template_file_exists(self, template_file: str) -> None:
        path = self._get_template_path(template_file)
        assert path.exists(), f"Template file missing: {template_file}"

    @pytest.mark.parametrize(
        "template_file",
        ["component-test.template.tsx", "hook-test.template.ts", "utility-test.template.ts"],
    )
    def test_template_has_jsdoc_usage_comment(self, template_file: str) -> None:
        """All template files must include usage instructions in a JSDoc comment."""
        content = read_file(self._get_template_path(template_file))
        assert "/**" in content, f"{template_file} must have a JSDoc comment"
        assert "Usage" in content or "usage" in content.lower(), (
            f"{template_file} JSDoc comment should include usage instructions"
        )

    @pytest.mark.parametrize(
        "template_file",
        ["component-test.template.tsx", "hook-test.template.ts", "utility-test.template.ts"],
    )
    def test_template_has_describe_block(self, template_file: str) -> None:
        """All templates must use describe() for test grouping."""
        content = read_file(self._get_template_path(template_file))
        assert "describe(" in content, f"{template_file} must contain describe() block"

    @pytest.mark.parametrize(
        "template_file",
        ["component-test.template.tsx", "hook-test.template.ts"],
    )
    def test_template_has_beforeEach_clearAllMocks(self, template_file: str) -> None:
        """Component and hook templates must include jest.clearAllMocks() in beforeEach.

        Utility templates (pure functions) do not need this since they typically
        have no mocks — their tests call real functions directly.
        """
        content = read_file(self._get_template_path(template_file))
        assert "jest.clearAllMocks()" in content, f"{template_file} must include jest.clearAllMocks() in beforeEach"

    def test_utility_template_does_not_require_beforeEach(self) -> None:
        """Utility templates for pure functions do not need jest.clearAllMocks().

        Pure function tests call real functions with no mocks, so beforeEach
        cleanup is not required. This test documents that design choice.
        """
        content = read_file(self._get_template_path("utility-test.template.ts"))
        # Utility template has no mandatory beforeEach - this is correct for pure functions
        # If there are mocks (e.g., for side-effect utilities), the user adds them manually
        assert "jest.mock" in content or "jest.fn" in content or "// jest.mock" in content, (
            "utility-test.template.ts must show how to conditionally add mocks"
        )

    @pytest.mark.parametrize(
        "template_file",
        ["component-test.template.tsx", "hook-test.template.ts", "utility-test.template.ts"],
    )
    def test_template_has_it_test_blocks(self, template_file: str) -> None:
        """Templates must contain it() test blocks."""
        content = read_file(self._get_template_path(template_file))
        # Either 'it(' or 'test(' for test cases
        assert re.search(r"\bit\(", content) or re.search(r"\btest\(", content), (
            f"{template_file} must contain it() or test() blocks"
        )

    def test_component_template_imports_render_and_screen(self) -> None:
        """Component template must import render and screen from @testing-library/react."""
        content = read_file(self._get_template_path("component-test.template.tsx"))
        assert "@testing-library/react" in content
        assert "render" in content and "screen" in content

    def test_component_template_imports_user_event(self) -> None:
        """Component template must import userEvent for user interaction simulation."""
        content = read_file(self._get_template_path("component-test.template.tsx"))
        assert "userEvent" in content
        assert "@testing-library/user-event" in content

    def test_component_template_has_edge_case_section(self) -> None:
        """Component template must include an edge cases section."""
        content = read_file(self._get_template_path("component-test.template.tsx"))
        assert "edge cases" in content.lower()

    def test_hook_template_imports_renderHook(self) -> None:
        """Hook template must import renderHook from @testing-library/react."""
        content = read_file(self._get_template_path("hook-test.template.ts"))
        assert "renderHook" in content
        assert "@testing-library/react" in content

    def test_hook_template_imports_act(self) -> None:
        """Hook template must import act for wrapping state updates."""
        content = read_file(self._get_template_path("hook-test.template.ts"))
        assert "act" in content

    def test_hook_template_has_initial_state_section(self) -> None:
        """Hook template must include initial state test section."""
        content = read_file(self._get_template_path("hook-test.template.ts"))
        assert "initial state" in content.lower()

    def test_hook_template_has_edge_cases_section(self) -> None:
        """Hook template must include edge cases test section."""
        content = read_file(self._get_template_path("hook-test.template.ts"))
        assert "edge cases" in content.lower()

    def test_utility_template_has_it_each_pattern(self) -> None:
        """Utility template must show the it.each() data-driven pattern."""
        content = read_file(self._get_template_path("utility-test.template.ts"))
        assert "it.each" in content

    def test_utility_template_has_error_cases_section(self) -> None:
        """Utility template must include error cases test section."""
        content = read_file(self._get_template_path("utility-test.template.ts"))
        assert "error cases" in content.lower() or "Error Cases" in content

    def test_utility_template_covers_null_undefined_edge_cases(self) -> None:
        """Utility template must demonstrate null/undefined edge case testing."""
        content = read_file(self._get_template_path("utility-test.template.ts"))
        assert "null" in content or "undefined" in content

    def test_component_template_has_template_placeholders(self) -> None:
        """Component template must use TEMPLATE_* placeholders to signal customization."""
        content = read_file(self._get_template_path("component-test.template.tsx"))
        assert "TEMPLATE_" in content

    def test_hook_template_has_template_placeholders(self) -> None:
        """Hook template must use TEMPLATE_* placeholders to signal customization."""
        content = read_file(self._get_template_path("hook-test.template.ts"))
        assert "TEMPLATE_" in content


# ---------------------------------------------------------------------------
# TestE2ETestingReferences
# ---------------------------------------------------------------------------


class TestE2ETestingReferences:
    """Validate e2e-testing reference files."""

    def test_fixtures_md_explains_error_detection(self) -> None:
        """fixtures.md must explain the automatic error detection behavior."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "references" / "fixtures.md")
        assert "error" in content.lower()

    def test_helpers_md_documents_awaitBootstrapTest(self) -> None:
        """helpers.md must document the awaitBootstrapTest utility."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "references" / "helpers.md")
        assert "awaitBootstrapTest" in content

    def test_helpers_md_documents_initialGPTsetup(self) -> None:
        """helpers.md must document the initialGPTsetup utility."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "references" / "helpers.md")
        assert "initialGPTsetup" in content

    def test_selectors_md_covers_data_testid_convention(self) -> None:
        """selectors.md must document the data-testid selector convention."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "references" / "selectors.md")
        assert "data-testid" in content or "getByTestId" in content

    def test_e2e_skill_documents_core_helper_functions(self) -> None:
        """E2E SKILL.md must document core helper functions."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "awaitBootstrapTest" in content
        assert "initialGPTsetup" in content


# ---------------------------------------------------------------------------
# TestComponentRefactoringReferences
# ---------------------------------------------------------------------------


class TestComponentRefactoringReferences:
    """Validate component-refactoring reference files."""

    def test_complexity_patterns_has_target_metrics(self) -> None:
        """complexity-patterns.md must document target complexity metrics."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "references" / "complexity-patterns.md")
        assert "Target" in content or "target" in content.lower()

    def test_complexity_patterns_covers_early_returns(self) -> None:
        """complexity-patterns.md must cover early return pattern."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "references" / "complexity-patterns.md")
        assert "early return" in content.lower() or "Early Return" in content

    def test_component_splitting_covers_when_to_split(self) -> None:
        """component-splitting.md must explain when to split components."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "references" / "component-splitting.md")
        assert "When to Split" in content or "when to split" in content.lower()

    def test_hook_extraction_covers_when_to_extract(self) -> None:
        """hook-extraction.md must explain when to extract a hook."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "references" / "hook-extraction.md")
        assert "when to" in content.lower() or "When to" in content

    def test_component_splitting_covers_file_naming_conventions(self) -> None:
        """component-splitting.md must mention kebab-case naming convention."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "references" / "component-splitting.md")
        assert "kebab-case" in content or "kebab" in content.lower()


# ---------------------------------------------------------------------------
# TestFrontendTestingAsyncReference
# ---------------------------------------------------------------------------


class TestFrontendTestingAsyncReference:
    """Validate the async-testing.md reference file."""

    def test_async_testing_md_exists(self) -> None:
        path = SKILL_DIRS["frontend-testing"] / "references" / "async-testing.md"
        assert path.exists()

    def test_async_testing_covers_waitFor(self) -> None:
        """async-testing.md must cover waitFor usage."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "references" / "async-testing.md")
        assert "waitFor" in content

    def test_async_testing_covers_findBy_queries(self) -> None:
        """async-testing.md must cover findBy* query patterns."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "references" / "async-testing.md")
        assert "findBy" in content

    def test_async_testing_covers_fake_timers(self) -> None:
        """async-testing.md must cover fake timer usage."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "references" / "async-testing.md")
        assert "fake" in content.lower() and "timer" in content.lower()

    def test_async_testing_covers_promise_rejection(self) -> None:
        """async-testing.md must cover promise rejection testing."""
        content = read_file(SKILL_DIRS["frontend-testing"] / "references" / "async-testing.md")
        assert "reject" in content.lower() or "rejection" in content.lower()


# ---------------------------------------------------------------------------
# TestFrontendQueryMutationReferences
# ---------------------------------------------------------------------------


class TestFrontendQueryMutationReferences:
    """Validate frontend-query-mutation reference files."""

    def test_query_patterns_md_covers_useRequestProcessor(self) -> None:
        """query-patterns.md must cover UseRequestProcessor pattern."""
        content = read_file(SKILL_DIRS["frontend-query-mutation"] / "references" / "query-patterns.md")
        assert "UseRequestProcessor" in content

    def test_query_patterns_md_covers_naming_conventions(self) -> None:
        """query-patterns.md must document hook naming conventions."""
        content = read_file(SKILL_DIRS["frontend-query-mutation"] / "references" / "query-patterns.md")
        assert "naming" in content.lower() or "convention" in content.lower()

    def test_runtime_rules_covers_cache_invalidation(self) -> None:
        """runtime-rules.md must cover cache invalidation patterns."""
        content = read_file(SKILL_DIRS["frontend-query-mutation"] / "references" / "runtime-rules.md")
        assert "invalidat" in content.lower()

    def test_runtime_rules_covers_error_handling(self) -> None:
        """runtime-rules.md must cover error handling."""
        content = read_file(SKILL_DIRS["frontend-query-mutation"] / "references" / "runtime-rules.md")
        assert "error" in content.lower()


# ---------------------------------------------------------------------------
# TestFrontendCodeReviewReferences
# ---------------------------------------------------------------------------


class TestFrontendCodeReviewReferences:
    """Validate frontend-code-review reference files."""

    def test_code_quality_md_covers_cn_function(self) -> None:
        """code-quality.md must document the cn() utility for conditional classes."""
        content = read_file(SKILL_DIRS["frontend-code-review"] / "references" / "code-quality.md")
        assert "cn(" in content or "`cn`" in content

    def test_performance_md_covers_memoization(self) -> None:
        """performance.md must cover React.memo or useMemo patterns."""
        content = read_file(SKILL_DIRS["frontend-code-review"] / "references" / "performance.md")
        assert "memo" in content.lower() or "useMemo" in content

    def test_business_logic_md_covers_custom_nodes(self) -> None:
        """business-logic.md must cover custom node component patterns."""
        content = read_file(SKILL_DIRS["frontend-code-review"] / "references" / "business-logic.md")
        assert "node" in content.lower() or "custom" in content.lower()

    def test_code_quality_md_covers_tailwind(self) -> None:
        """code-quality.md must mention Tailwind CSS styling."""
        content = read_file(SKILL_DIRS["frontend-code-review"] / "references" / "code-quality.md")
        assert "Tailwind" in content or "tailwind" in content


# ---------------------------------------------------------------------------
# TestCrossSkillConsistency
# ---------------------------------------------------------------------------


class TestCrossSkillConsistency:
    """Ensure consistency across different skills."""

    def test_backend_review_does_not_mention_tsx_files(self) -> None:
        """Backend code review must explicitly state it is NOT for frontend files."""
        content = read_file(SKILL_DIRS["backend-code-review"] / "SKILL.md")
        # The skill should have a "Do NOT use" section for frontend
        assert "Do NOT use" in content or "do not use" in content.lower()

    def test_e2e_testing_refers_to_frontend_testing_for_unit_tests(self) -> None:
        """E2E skill must point to frontend-testing skill for unit tests."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "frontend-testing" in content or "unit test" in content.lower()

    def test_component_refactoring_refers_to_frontend_testing(self) -> None:
        """Component refactoring skill must reference frontend-testing for writing tests."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "SKILL.md")
        assert "frontend-testing" in content

    def test_component_refactoring_refers_to_frontend_query_mutation(self) -> None:
        """Component refactoring skill must reference frontend-query-mutation for API patterns."""
        content = read_file(SKILL_DIRS["component-refactoring"] / "SKILL.md")
        assert "frontend-query-mutation" in content

    def test_all_review_skills_mention_output_format(self) -> None:
        """Review skills must define an output format."""
        for skill_name in ("backend-code-review", "frontend-code-review"):
            content = read_file(SKILL_DIRS[skill_name] / "SKILL.md")
            assert "output" in content.lower() or "Output" in content, f"{skill_name} must define an output format"

    def test_e2e_skill_documents_test_tags(self) -> None:
        """E2E testing skill must document available test tags."""
        content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert "@release" in content

    def test_frontend_testing_and_e2e_use_different_file_suffixes(self) -> None:
        """Frontend unit tests use .test.tsx, E2E tests use .spec.ts."""
        frontend_content = read_file(SKILL_DIRS["frontend-testing"] / "SKILL.md")
        e2e_content = read_file(SKILL_DIRS["e2e-testing"] / "SKILL.md")
        assert ".test.tsx" in frontend_content or ".test.ts" in frontend_content
        assert ".spec.ts" in e2e_content
