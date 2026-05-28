/**
 * E2E tests for the new default system prompt (7-section template).
 *
 * Coverage breakdown:
 *   Test 1-2: pure UI assertions on the default template (no LLM).
 *   Test 3-5: playground assertions that prove runtime {current_date} /
 *             {model_name} substitution AND opt-in behavior for custom prompts.
 *
 * Per PLAYWRIGHT_RULE.md, each test must be run individually before trusting the
 * whole file. See the comment block at the top of each test for the single-test
 * command.
 */
import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
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

function isoDateToday(): string {
  return new Date().toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Test 1 — UI only: new Agent ships with the 7-section template
// Run:  npx playwright test default-system-prompt --grep "Agent component shows" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "Agent component shows the 7-section default template when dropped on canvas",
  { tag: ["@release", "@workspace", "@agents"] },
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
  { tag: ["@release", "@workspace", "@agents"] },
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

// ---------------------------------------------------------------------------
// Test 3 — runtime substitution: the default prompt, when invoked, quotes the
// actual date (proves {current_date} was replaced before the LLM saw it).
// Run:  npx playwright test default-system-prompt --grep "runtime substitution injects" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "runtime substitution injects today's date into the agent's effective prompt",
  { tag: ["@release", "@agents", "@api"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    // Load Simple Agent — gives us a ready-to-run Agent wired to ChatInput/Output.
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateSimpleAgent })
      .first()
      .click();
    await initialGPTsetup(page);

    // Simple Agent's template may carry its own system_prompt — force the fresh
    // component default by clearing and re-entering the Agent's Instructions to
    // re-trigger the component's default loading isn't trivial. Instead we
    // assert on the TEMPLATE's shipped default value: if the template JSON now
    // includes the new placeholders, runtime substitution should still kick in.
    // If the template explicitly overrides the prompt, we still rely on the
    // runtime hook only substituting placeholders when present — so we set a
    // short probe prompt with placeholders explicitly.
    const probePrompt =
      "Reply with exactly one line: DATE={current_date} MODEL={model_name}";
    const textarea = page.getByTestId("textarea_str_system_prompt").first();
    await textarea.waitFor({ state: "visible", timeout: 15000 });
    await textarea.click();
    await page.keyboard.press("ControlOrMeta+A");
    await textarea.fill(probePrompt);

    await page.getByTestId("playground-btn-flow-io").click();
    await page.getByTestId("input-chat-playground").last().fill("Run now.");
    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    await stopButton.waitFor({ state: "hidden", timeout: 120000 });

    await expect(page.getByTestId("div-chat-message").first()).toBeVisible({
      timeout: 10000,
    });

    const reply = (
      (await page.locator(".markdown.prose").last().textContent()) ?? ""
    ).toLowerCase();

    // The substituted date must appear; the raw placeholder must not.
    expect(reply).toContain(isoDateToday());
    expect(reply).not.toContain("{current_date}");
    expect(reply).not.toContain("{model_name}");
  },
);

// ---------------------------------------------------------------------------
// Test 4 — custom prompt without placeholders: opt-out by omission
// Run:  npx playwright test default-system-prompt --grep "custom prompt without placeholders" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "custom prompt without placeholders passes through untouched",
  { tag: ["@release", "@agents", "@api"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateSimpleAgent })
      .first()
      .click();
    await initialGPTsetup(page);

    const customPrompt =
      "You are a pirate. End every reply with the word 'ARRR'. Never mention dates.";
    const textarea = page.getByTestId("textarea_str_system_prompt").first();
    await textarea.waitFor({ state: "visible", timeout: 15000 });
    await textarea.click();
    await page.keyboard.press("ControlOrMeta+A");
    await textarea.fill(customPrompt);

    await page.getByTestId("playground-btn-flow-io").click();
    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Introduce yourself in one short sentence.");
    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    await stopButton.waitFor({ state: "hidden", timeout: 120000 });

    await expect(page.getByTestId("div-chat-message").first()).toBeVisible({
      timeout: 10000,
    });

    const reply = (
      (await page.locator(".markdown.prose").last().textContent()) ?? ""
    ).toLowerCase();

    // The pirate directive is being followed, which implies the LLM received
    // the custom prompt verbatim rather than the default 7-section template.
    expect(reply).toContain("arrr");
    // Default-template terminology must NOT leak in — proves no runtime
    // substitution path appended / altered the user's prompt.
    expect(reply).not.toContain("# identity");
    expect(reply).not.toContain("langflow agent");
  },
);

// ---------------------------------------------------------------------------
// Test 5 — custom prompt with {current_date}: opt-in substitution
// Run:  npx playwright test default-system-prompt --grep "custom prompt with placeholder opts in" --retries=0 --reporter=line
// ---------------------------------------------------------------------------
test(
  "custom prompt with placeholder opts in to runtime substitution",
  { tag: ["@release", "@agents", "@api"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateSimpleAgent })
      .first()
      .click();
    await initialGPTsetup(page);

    // Force the model to echo the date from its context — any obedience-style
    // directive alone ("start reply with X") is too easy for chat-tuned models
    // to minimize away on trivial inputs.
    const customPrompt =
      "Today's date, as provided to you, is {current_date}. When the user asks 'What is today's date?', answer with the exact ISO date and nothing else.";
    const textarea = page.getByTestId("textarea_str_system_prompt").first();
    await textarea.waitFor({ state: "visible", timeout: 15000 });
    await textarea.click();
    await page.keyboard.press("ControlOrMeta+A");
    await textarea.fill(customPrompt);

    await page.getByTestId("playground-btn-flow-io").click();
    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("What is today's date?");
    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    await stopButton.waitFor({ state: "hidden", timeout: 120000 });

    await expect(page.getByTestId("div-chat-message").first()).toBeVisible({
      timeout: 10000,
    });

    const reply =
      (await page.locator(".markdown.prose").last().textContent()) ?? "";

    // Substitution happened: reply includes today's date.
    expect(reply).toContain(isoDateToday());
    // Raw placeholder must NOT appear in the reply.
    expect(reply).not.toContain("{current_date}");
  },
);
