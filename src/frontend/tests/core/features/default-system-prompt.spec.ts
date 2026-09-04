/**
 * E2E tests for the new default system prompt (7-section template).
 *
 * Runtime placeholder substitution is covered in the LFX unit suite. These
 * browser tests intentionally keep only the structural UI contract.
 *
 * Per PLAYWRIGHT_RULE.md, each test must be run individually before trusting the
 * whole file. See the comment block at the top of each test for the single-test
 * command.
 */
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

// Every section header the new default template must contain, in order.
const SECTION_HEADERS = [
  "# Identity",
  "# Safety",
  "# Using tools",
  "# Doing tasks",
  "# Action safety",
  "# Tone",
  "# Environment",
];

// ---------------------------------------------------------------------------
// Test 1 — UI only: new Agent ships with the 7-section template
// Run:  npx playwright test default-system-prompt --grep "Agent component shows" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "Agent component shows the 7-section default template when dropped on canvas",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    await zoomOut(page, 3);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("agent");
    await page.waitForSelector('[data-testid="models_and_agentsAgent"]', {
      timeout: 5000,
    });

    await page
      .getByTestId("models_and_agentsAgent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 300 },
      });

    await adjustScreenView(page);

    const textarea = page.getByTestId("textarea_str_system_prompt").first();
    await textarea.waitFor({ state: "visible", timeout: 15000 });
    const value = (await textarea.inputValue()) ?? "";

    // Structural assertions — prove the new template replaced the old one-liner.
    expect(value).not.toContain(
      "You are a helpful assistant that can use tools to answer questions and perform tasks.",
    );
    for (const header of SECTION_HEADERS) {
      expect(value).toContain(header);
    }
    // Placeholders are expected as literal text in the UI (render happens at runtime).
    expect(value).toContain("{current_date}");
    expect(value).toContain("{model_name}");
    // Tool list anti-pattern must be absent.
    expect(value).not.toContain("{tools}");
  },
);

// ---------------------------------------------------------------------------
// Test 2 — UI only: Tool Calling Agent also ships with the new template
// Run:  npx playwright test default-system-prompt --grep "Tool Calling Agent component shows" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "Tool Calling Agent component shows the 7-section default template when dropped on canvas",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    await zoomOut(page, 3);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("tool calling agent");
    await page.waitForSelector(
      '[data-testid="langchain_utilitiesTool Calling Agent"]',
      { timeout: 5000 },
    );

    await page
      .getByTestId("langchain_utilitiesTool Calling Agent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 300 },
      });

    await adjustScreenView(page);

    // ToolCallingAgent uses MessageTextInput (single-line). The testid
    // `popover-anchor-input-system_prompt` is applied directly on the <input>
    // element (see CustomInputPopover), so no descendant lookup is needed.
    const inputLocator = page
      .getByTestId("popover-anchor-input-system_prompt")
      .first();
    await inputLocator.waitFor({ state: "visible", timeout: 15000 });
    const value = (await inputLocator.inputValue()) ?? "";

    expect(value).not.toContain(
      "You are a helpful assistant that can use tools to answer questions and perform tasks.",
    );
    for (const header of SECTION_HEADERS) {
      expect(value).toContain(header);
    }
    expect(value).toContain("{current_date}");
    expect(value).toContain("{model_name}");
    expect(value).not.toContain("{tools}");
  },
);
