import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { mockAssistant } from "../../utils/mock-assistant";

async function openAssistantComposer(page: Page) {
  await mockAssistant(page);
  await openStarterProject(page, "Basic Prompting");
  await page.getByTestId("assistant-button").click();
  const textarea = page.getByTestId("assistant-input-textarea");
  await expect(textarea).toBeVisible();
  await textarea.click();
  return textarea;
}

test.describe("Assistant slash command menu", { tag: ["@release"] }, () => {
  test("should insert the command picked with arrow keys and Enter", async ({
    page,
  }) => {
    const assistantRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/agentic/assist")) {
        assistantRequests.push(request.url());
      }
    });
    const textarea = await openAssistantComposer(page);

    await textarea.pressSequentially("/");
    const listbox = page.getByRole("listbox", { name: "Assistant commands" });
    await expect(listbox.getByRole("option")).toHaveCount(3);
    await expect(textarea).toHaveAttribute(
      "aria-activedescendant",
      /skip-all$/,
    );

    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await expect(
      page.getByTestId("assistant-slash-command-option-iterations"),
    ).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("Enter");

    await expect(listbox).toBeHidden();
    await expect(textarea).toHaveValue("/iterations ");
    await expect(textarea).toBeFocused();
    await expect(page.getByText("Iteration budget:")).toHaveCount(0);

    await page.keyboard.press("Enter");
    await expect(
      page.getByText("Iteration budget: default (100).", { exact: false }),
    ).toBeVisible();
    await expect(textarea).toHaveValue("");
    expect(assistantRequests).toEqual([]);
  });

  test("should complete with Tab so an argument can be typed", async ({
    page,
  }) => {
    const textarea = await openAssistantComposer(page);

    await textarea.pressSequentially("/hi");
    await expect(
      page.getByTestId("assistant-slash-command-option-history"),
    ).toBeVisible();
    await page.keyboard.press("Tab");

    await expect(textarea).toHaveValue("/history ");
    await expect(textarea).toBeFocused();
    await expect(page.getByRole("listbox")).toBeHidden();

    await textarea.pressSequentially("5");
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("History limit set to 5 message(s) for this session."),
    ).toBeVisible();
  });

  test("should close on Escape and keep the draft", async ({ page }) => {
    const textarea = await openAssistantComposer(page);

    await textarea.pressSequentially("/it");
    await expect(page.getByRole("listbox")).toBeVisible();
    await page.keyboard.press("Escape");

    await expect(page.getByRole("listbox")).toBeHidden();
    await expect(textarea).toHaveValue("/it");
    await expect(textarea).toBeFocused();
  });

  test("should close the menu when the draft is sent with the Send button", async ({
    page,
  }) => {
    const textarea = await openAssistantComposer(page);
    // A session that already has messages keeps the composer mounted after sending.
    await textarea.pressSequentially("/iterations");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Iteration budget:")).toBeVisible();
    // The first message swaps the compact composer for the conversation layout;
    // wait for the remounted, empty textarea before typing into it.
    await expect(textarea).toHaveValue("");
    await textarea.click();

    const popover = page.getByTestId("assistant-slash-command-popover");
    await textarea.pressSequentially("/");
    await expect(popover).toBeVisible();
    await page.getByTestId("assistant-send-button").click();

    await expect(textarea).toHaveValue("");
    await expect(popover).toBeHidden();
    await expect(textarea).not.toHaveAttribute("aria-activedescendant");
  });

  test("should close the menu when focus moves to another control", async ({
    page,
  }) => {
    const textarea = await openAssistantComposer(page);

    const popover = page.getByTestId("assistant-slash-command-popover");
    await textarea.pressSequentially("/");
    await expect(popover).toBeVisible();
    // Query by test id: the model dropdown hides the rest of the page from role queries.
    await page.getByTestId("assistant-model-selector").click();

    await expect(popover).toBeHidden();
  });

  test("should pass the live accessibility scan with the menu open", async ({
    page,
  }) => {
    const textarea = await openAssistantComposer(page);

    await textarea.pressSequentially("/");
    await page.keyboard.press("ArrowDown");
    await expect(
      page.getByTestId("assistant-slash-command-option-history"),
    ).toHaveAttribute("aria-selected", "true");

    await page.runA11yScan("assistant-slash-command-menu-open");
  });
});
