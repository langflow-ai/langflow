import { expect, test } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import {
  type AssistantMockController,
  mockAssistant,
} from "../../utils/mock-assistant";

test.describe("Assistant Panel Integration", { tag: ["@release"] }, () => {
  let assistantMock: AssistantMockController;

  test.beforeEach(async ({ page }) => {
    assistantMock = await mockAssistant(page);
    await openStarterProject(page, "Basic Prompting");

    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).toBeVisible();
    await expect(page.getByTestId("assistant-model-selector")).toContainText(
      "gpt-4o-mini",
    );
  });

  test("should answer a Q&A question from the mocked SSE stream", async ({
    page,
  }) => {
    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("What is Langflow? Answer in one sentence.");
    await page.getByTestId("assistant-send-button").click();

    await expect(page.getByTestId("assistant-message-user")).toContainText(
      "What is Langflow",
    );
    await expect(
      page.getByTestId("assistant-message-assistant").last(),
    ).toContainText("Langflow is a deterministic visual workflow builder.");
    await expect(textarea).toBeEnabled();
  });

  test("should generate a component and approve it onto the canvas", async ({
    page,
  }) => {
    const nodes = page.locator(".react-flow__node");
    const initialNodeCount = await nodes.count();
    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill(
      "Create a simple component that takes a text input and returns it uppercase",
    );
    await page.getByTestId("assistant-send-button").click();

    await expect(
      page.getByText("UppercaseText", { exact: true }),
    ).toBeVisible();
    await expect(page.getByTestId("assistant-approve-button")).toBeVisible();

    const validationResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith("/api/v1/custom_component"),
    );
    await page.getByTestId("assistant-approve-button").click();
    expect((await validationResponse).ok()).toBeTruthy();

    await expect(page.getByTestId("assistant-panel")).not.toBeVisible();
    await expect(nodes).toHaveCount(initialNodeCount + 1);
  });

  test("should show deterministic component code via View Code", async ({
    page,
  }) => {
    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("Create a component that reverses a string input");
    await page.getByTestId("assistant-send-button").click();

    await expect(page.getByTestId("assistant-view-code-button")).toBeVisible();
    await page.getByTestId("assistant-view-code-button").click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("class UppercaseText");

    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
  });

  test("should stop a pending generation", async ({ page }) => {
    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill(
      "Write a very detailed 2000-word essay about the history of computing",
    );
    await page.getByTestId("assistant-send-button").click();

    const stopButton = page.getByTestId("assistant-stop-button");
    await expect(stopButton).toBeVisible();
    await stopButton.click();
    assistantMock.releaseCancelledRequest();

    await expect(stopButton).not.toBeVisible();
    await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
    await expect(textarea).toBeEnabled();
  });

  test("should clear history and reset the backend session", async ({
    page,
  }) => {
    const textarea = page.getByTestId("assistant-input-textarea");
    await textarea.fill("Say hello");
    await page.getByTestId("assistant-send-button").click();

    await expect(
      page.getByTestId("assistant-message-assistant").last(),
    ).toContainText("Langflow is a deterministic visual workflow builder.");
    await expect(page.getByTestId("assistant-new-session")).toBeEnabled();

    await assistantMock.armSessionReset();
    const resetRequest = assistantMock.waitForSessionReset();
    await page.getByTestId("assistant-new-session").click();
    const resetUrl = await resetRequest;
    expect(resetUrl.origin).toBe(new URL(page.url()).origin);
    expect(resetUrl.pathname).toBe("/api/v1/agentic/sessions/reset");
    expect(resetUrl.searchParams.get("session_id")).toMatch(/^agentic_/);

    await expect(page.getByTestId("assistant-message-user")).not.toBeVisible();
    await expect(
      page.getByTestId("assistant-message-assistant"),
    ).not.toBeVisible();
    await expect(page.getByTestId("assistant-new-session")).toBeDisabled();
  });
});
