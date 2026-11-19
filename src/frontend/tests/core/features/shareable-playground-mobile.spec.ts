import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";

// Height of an Android navigation bar drawn over an edge-to-edge window.
const NAVIGATION_BAR = 48;

async function createPublicChatFlow(page: Page): Promise<string> {
  const all = (await (await page.request.get("/api/v1/all")).json()) as Record<
    string,
    Record<string, unknown>
  >;
  const chatInput = Object.values(all).find((c) => "ChatInput" in c)?.ChatInput;
  expect(chatInput).toBeTruthy();
  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `shared-mobile-${Date.now()}`,
      access_type: "PUBLIC",
      data: {
        nodes: [
          {
            id: "ChatInput-mobile",
            type: "genericNode",
            position: { x: 0, y: 0 },
            data: {
              id: "ChatInput-mobile",
              type: "ChatInput",
              node: chatInput,
            },
          },
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  expect(created.status()).toBe(201);
  return (await created.json()).id;
}

async function expectAboveNavigationBar(page: Page, testId: string) {
  const box = await page.getByTestId(testId).last().boundingBox();
  const height = await page.evaluate(() => window.innerHeight);
  expect(box, `${testId} should be rendered`).not.toBeNull();
  expect(box!.y + box!.height, `${testId} bottom edge`).toBeLessThanOrEqual(
    height - NAVIGATION_BAR,
  );
}

test.use({ viewport: { width: 412, height: 839 }, isMobile: true });

test(
  "shareable playground on a phone keeps the chat input above the navigation bar",
  { tag: ["@release"] },
  async ({ page, browserName }) => {
    test.skip(
      browserName !== "chromium",
      "Safe-area insets are emulated through the Chrome DevTools Protocol",
    );
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createPublicChatFlow(page);

    try {
      const cdp = await page.context().newCDPSession(page);
      await cdp.send("Emulation.setSafeAreaInsetsOverride", {
        insets: { bottom: NAVIGATION_BAR, bottomMax: NAVIGATION_BAR },
      });
      await page.goto(`/playground/${flowId}`);
      await page
        .getByPlaceholder(TEXTS.placeholderSendMessage)
        .waitFor({ state: "visible", timeout: TIMEOUTS.long });

      // Without viewport-fit=cover a device reports no insets to the page.
      await expect(page.locator('meta[name="viewport"]')).toHaveAttribute(
        "content",
        /viewport-fit=cover/,
      );
      await expectAboveNavigationBar(page, TID.inputChatPlayground);
      await expectAboveNavigationBar(page, TID.buttonSend);
    } finally {
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);
