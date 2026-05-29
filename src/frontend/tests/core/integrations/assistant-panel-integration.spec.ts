import { expect, test } from "../../fixtures";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { selectAssistantOpenAiModel } from "../../utils/select-assistant-openai-model";

test.describe("Assistant Panel Integration", { tag: ["@release"] }, () => {
  test.beforeEach(async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Basic Prompting");

    // Open assistant panel and wait for model selector
    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).toBeVisible();
    await expect(page.getByTestId("assistant-model-selector")).toBeVisible({
      timeout: 15000,
    });
    await selectAssistantOpenAiModel(page);
  });

  test("should answer a Q&A question with real LLM response", async ({
    page,
  }) => {
    test.setTimeout(120_000);

    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("What is Langflow? Answer in one sentence.");
    await page.getByTestId("assistant-send-button").click();

    // User message should appear
    await expect(
      page.getByTestId("assistant-message-user").first(),
    ).toContainText("What is Langflow");

    // Wait for assistant response wrapper to appear (locator.waitFor respects
    // its own timeout; page.waitForFunction is capped by actionTimeout=20s
    // per PLAYWRIGHT_RULE.md #4).
    await page
      .getByTestId("assistant-message-assistant")
      .last()
      .waitFor({ state: "visible", timeout: 90000 });

    // Input should be re-enabled after response completes
    await expect(textarea).toBeEnabled({ timeout: 10000 });
  });

  test("should generate a component and allow approval", async ({ page }) => {
    test.setTimeout(180_000);

    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill(
      "Create a simple component that takes a text input and returns it uppercase",
    );
    await page.getByTestId("assistant-send-button").click();

    await expect(
      page.getByTestId("assistant-message-user").first(),
    ).toContainText("uppercase");

    // Wait for a TERMINAL generation state before branching. With a real LLM
    // the run is non-deterministic: it either builds a component (the
    // component-result card renders) or answers with plain text (the input
    // re-enables). Both are terminal. We must NOT race on
    // `assistant-message-assistant` — that wrapper mounts MID-STREAM, before the
    // component card renders and before the input re-enables, so branching on it
    // checks `componentResult.count()` too early and trips on the still-disabled
    // "Generating component..." textarea.
    //
    // `Promise.any` resolves on the FIRST terminal signal and only rejects if
    // BOTH time out (a truly hung generation). `locator.waitFor` /
    // `expect().toBeEnabled()` respect their own timeouts (page.waitForFunction
    // would be capped at actionTimeout=20s per PLAYWRIGHT_RULE #4).
    const componentResult = page.getByTestId("assistant-component-result");
    await Promise.any([
      componentResult.waitFor({ state: "visible", timeout: 150000 }),
      expect(textarea).toBeEnabled({ timeout: 150000 }),
    ]);

    const hasComponentResult = (await componentResult.count()) > 0;

    if (hasComponentResult) {
      await expect(
        page.getByTestId("assistant-view-code-button"),
      ).toBeVisible();
      await expect(page.getByTestId("assistant-approve-button")).toBeVisible();

      // Approve adds to canvas and closes panel
      await page.getByTestId("assistant-approve-button").click();
      await expect(page.getByTestId("assistant-panel")).not.toBeVisible({
        timeout: 5000,
      });

      const nodes = page.locator(".react-flow__node");
      await expect(nodes).not.toHaveCount(0, { timeout: 5000 });
    } else {
      await expect(textarea).toBeEnabled({ timeout: 10000 });
    }
  });

  test("should show component code via View Code", async ({ page }) => {
    test.setTimeout(180_000);

    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("Create a component that reverses a string input");
    await page.getByTestId("assistant-send-button").click();

    // page.waitForFunction is capped at actionTimeout=20s (PLAYWRIGHT_RULE #4);
    // use locator.waitFor which respects its own timeout.
    await Promise.race([
      page
        .getByTestId("assistant-component-result")
        .waitFor({ state: "visible", timeout: 150000 }),
      page
        .getByTestId("assistant-message-assistant")
        .last()
        .waitFor({ state: "visible", timeout: 150000 }),
    ]);

    const hasComponentResult =
      (await page.getByTestId("assistant-component-result").count()) > 0;

    if (hasComponentResult) {
      await page.getByTestId("assistant-view-code-button").click();

      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: 5000 });
      await expect(dialog).toContainText("class", { timeout: 5000 });

      await page.keyboard.press("Escape");
      await expect(dialog).not.toBeVisible({ timeout: 3000 });
    }
  });

  test("should stop generation mid-stream", async ({ page }) => {
    test.setTimeout(120_000);

    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill(
      "Write a very detailed 2000-word essay about the history of computing",
    );
    await page.getByTestId("assistant-send-button").click();

    // Wait for either the stop button (streaming in progress) or
    // an assistant response (streaming completed before we could catch it)
    const stopButton = page.getByTestId("assistant-stop-button");
    const assistantMessage = page.getByTestId("assistant-message-assistant");

    const result = await Promise.race([
      stopButton
        .waitFor({ state: "visible", timeout: 30000 })
        .then(() => "stop-visible" as const),
      assistantMessage
        .waitFor({ state: "visible", timeout: 30000 })
        .then(() => "response-complete" as const),
    ]);

    if (result === "stop-visible") {
      // Streaming is still in progress - click stop
      await stopButton.click();

      await expect(stopButton).not.toBeVisible({ timeout: 5000 });
      await expect(page.getByText("Cancelled")).toBeVisible({ timeout: 5000 });
    }

    // In both cases, input should be re-enabled
    await expect(textarea).toBeEnabled({ timeout: 10000 });
    await expect(page.getByTestId("assistant-send-button")).toBeVisible();
  });

  test("should clear history with new session", async ({ page }) => {
    test.setTimeout(120_000);

    await expect(page.getByTestId("assistant-new-session")).toBeDisabled();

    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("Say hello");
    await page.getByTestId("assistant-send-button").click();

    await expect(
      page.getByTestId("assistant-message-user").first(),
    ).toBeVisible();

    // Wait for assistant response wrapper to appear (locator.waitFor respects
    // its own timeout; page.waitForFunction is capped at actionTimeout=20s
    // per PLAYWRIGHT_RULE.md #4).
    await page
      .getByTestId("assistant-message-assistant")
      .last()
      .waitFor({ state: "visible", timeout: 90000 });

    await expect(textarea).toBeEnabled({ timeout: 10000 });
    await expect(page.getByTestId("assistant-new-session")).toBeEnabled();

    // Clear history
    await page.getByTestId("assistant-new-session").click();

    await expect(page.getByTestId("assistant-message-user")).not.toBeVisible();
    await expect(
      page.getByTestId("assistant-message-assistant"),
    ).not.toBeVisible();
    await expect(page.getByTestId("assistant-new-session")).toBeDisabled();
    await expect(textarea).toBeVisible();
  });
});
