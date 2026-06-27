import type { Page } from "@playwright/test";
import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

type MemoryBaseCreateResponse = {
  id: string;
  name: string;
};

function getCurrentFlowId(page: Page): string {
  const flowId = page.url().match(/\/flow\/([^/?#]+)/)?.[1];
  if (!flowId) {
    throw new Error(`Could not read flow id from ${page.url()}`);
  }
  return flowId;
}

async function createMemoryBase(page: Page, flowId: string, name: string) {
  const response = await page.request.post("/api/v1/memories/", {
    data: {
      name,
      flow_id: flowId,
      embedding_model: "text-embedding-3-small",
      threshold: 1,
      auto_capture: false,
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as MemoryBaseCreateResponse;
}

async function selectMemoryBase(page: Page, memoryBaseName: string) {
  const memoryBaseNode = page
    .locator(".react-flow__node")
    .filter({ hasText: "Memory Base" })
    .first();
  await expect(memoryBaseNode).toBeVisible({ timeout: 30000 });
  await memoryBaseNode.click();
  const memoryDropdown = page.getByTestId("dropdown_str_memory_base");

  await memoryDropdown.click();
  if ((await page.getByText(memoryBaseName, { exact: true }).count()) === 0) {
    await page.getByTestId("refresh-dropdown-list-memory_base").click();
    await expect(memoryDropdown).toBeVisible({ timeout: 30000 });
    await memoryDropdown.click();
  }

  await page.getByTestId("dropdown_search_input").fill(memoryBaseName);
  await page.getByTestId("dropdown-option-0-container").click();
  await expect(
    page.getByTestId("value-dropdown-dropdown_str_memory_base"),
  ).toContainText(memoryBaseName);
}

withEventDeliveryModes(
  "Memory Chatbot",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    const memoryBaseName = `memory_chatbot_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    let memoryBaseId: string | undefined;

    try {
      await openStarterProject(page, "Memory Chatbot");
      await page.waitForURL(/\/flow\/[^/?#]+/, { timeout: 100000 });
      await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
        timeout: 100000,
      });
      const memoryBase = await createMemoryBase(
        page,
        getCurrentFlowId(page),
        memoryBaseName,
      );
      memoryBaseId = memoryBase.id;
      await initialGPTsetup(page);
      await selectMemoryBase(page, memoryBase.name);

      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();

      await page
        .getByText(TEXTS.labelNoInputMessage, { exact: true })
        .last()
        .isVisible();

      await sendPlaygroundMessage(
        page,
        "In one sentence, explain what long-term memory helps with.",
      );

      const textContents = await getAllResponseMessage(page);
      expect(textContents.length).toBeGreaterThan(20);
      expect(textContents).toContain("memory");

      // Open message logs from session sidebar menu (chat-header-more-menu is hidden in fullscreen)
      await page
        .locator('[data-testid^="session-"][data-testid$="-more-menu"]')
        .first()
        .click();
      await page.getByTestId("message-logs-option").click();

      await expect(page.getByText("timestamp", { exact: true })).toBeVisible();
      await expect(page.getByText("text", { exact: true })).toBeVisible();
      await expect(page.getByText("sender", { exact: true })).toBeVisible();
      await expect(
        page.getByText("sender_name", { exact: true }),
      ).toBeVisible();
      await expect(page.getByText("session_id", { exact: true })).toBeVisible();
      await expect(page.getByText("files", { exact: true })).toBeVisible();
    } finally {
      if (memoryBaseId) {
        await page.request
          .delete(`/api/v1/memories/${memoryBaseId}`)
          .catch(() => undefined);
      }
    }
  },
);
