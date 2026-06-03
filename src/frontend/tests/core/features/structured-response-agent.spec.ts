import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { openAdvancedOptions } from "../../utils/open-advanced-options";

/**
 * E2E coverage for the Native Structured Output feature on the Agent
 * component (CZL/MANUAL_TEST_NATIVE_STRUCTURED_OUTPUT.md). The tests
 * exercise the UI infrastructure that ALL manual scenarios A–G depend on:
 *
 *   - Slice 10 — Agent declares the structured_response output (every
 *     scenario wires this handle).
 *   - hidden-fields.ts fix — Output Schema + Format Instructions are
 *     reachable in the inspection panel (scenarios A/D/E/F/G setup).
 *   - Output dropdown swap — switching to Structured Response routes the
 *     existing wire through json_response without dropping the edge.
 *
 * Backend pytest suites cover the runtime orchestration. These Playwright
 * tests guard the UI wiring so a regression in the Agent inputs list, the
 * inspection panel filter, or the output handle declaration is caught in
 * the release gate.
 */

test(
  "manual scenarios A–G prerequisite — Agent exposes structured_response output handle alongside response",
  { tag: ["@release", "@workspace", "@components"] },
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

    // The Agent declares two outputs (Response, Structured Response). On the
    // canvas they share a single combobox-style dropdown keyed by the
    // component name — the testid resolves to "dropdown-output-undefined"
    // because Simple Agent's cached node ships with `data.node.key === null`.
    const outputDropdown = page
      .getByTestId("dropdown-output-undefined")
      .first();
    await expect(outputDropdown).toBeVisible({ timeout: 30000 });

    // The dropdown shows the currently selected output (Response by default).
    await expect(outputDropdown).toContainText("Response", { timeout: 10000 });

    // Opening it must list the Structured Response option — without Slice 10
    // the user could not wire the orchestrator path.
    await outputDropdown.click();
    await expect(
      page.getByTestId("dropdown-item-output-undefined-structured response"),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByTestId("dropdown-item-output-undefined-response"),
    ).toBeVisible({ timeout: 10000 });
  },
);

test(
  "manual scenarios A/D/E/F/G setup — inspection panel exposes Output Schema and Output Format Instructions",
  { tag: ["@release", "@workspace", "@components"] },
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

    // Focus the Agent node so the inspection panel reflects its fields.
    const agentNode = page
      .locator(".react-flow__node")
      .filter({ has: page.getByTestId("title-Agent") })
      .first();
    await agentNode.click();

    await openAdvancedOptions(page);

    // Both fields must be reachable so the user can fill the schema and
    // format instructions for scenarios A, E, F, G — and clear the schema
    // for scenario D. Before the hidden-fields.ts fix these IDs were
    // filtered out of the inspection panel and the feature was unreachable.
    await expect(page.locator('//*[@id="showoutput_schema"]')).toBeVisible({
      timeout: 10000,
    });
    await expect(
      page.locator('//*[@id="showformat_instructions"]'),
    ).toBeVisible({ timeout: 10000 });
  },
);

test(
  "scenarios A–C wiring — switching the agent dropdown to Structured Response keeps the downstream edge",
  { tag: ["@release", "@workspace", "@components"] },
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

    await adjustScreenView(page);

    const outputDropdown = page
      .getByTestId("dropdown-output-undefined")
      .first();
    await expect(outputDropdown).toBeVisible({ timeout: 30000 });

    // Switch the agent's selected output to Structured Response — this is
    // the user gesture every "structured" manual scenario starts from.
    await outputDropdown.click();
    await page
      .getByTestId("dropdown-item-output-undefined-structured response")
      .click({ force: true });

    // After the swap the dropdown trigger reflects the new selection.
    await expect(outputDropdown).toContainText("Structured Response", {
      timeout: 10000,
    });

    // The downstream Chat Output edge must remain intact — the swap reroutes
    // the same edge through json_response. Re-opening the dropdown must
    // still surface both options so the user can revert if needed.
    await outputDropdown.click();
    await expect(
      page.getByTestId("dropdown-item-output-undefined-response"),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByTestId("dropdown-item-output-undefined-structured response"),
    ).toBeVisible({ timeout: 10000 });
  },
);
