import type { Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";
import type { LangflowPage } from "../utils/types";

type MessageRow = {
  id: string;
  timestamp: string;
  text: string;
  sender: string;
  sender_name: string;
  session_id: string;
};

const firstMessageText = "Hey there! 👋 Great to see you here.";

const populatedMessages: MessageRow[] = [
  {
    id: "a11y-message-1",
    timestamp: "2026-07-14T12:00:00.000Z",
    text: firstMessageText,
    sender: "User",
    sender_name: "Accessibility reviewer",
    session_id: "a11y-session-1",
  },
  {
    id: "a11y-message-2",
    timestamp: "2026-07-14T12:00:01.000Z",
    text: "The route has no automated accessibility violations.",
    sender: "Machine",
    sender_name: "Assistant",
    session_id: "a11y-session-1",
  },
];

async function mockMessages(page: LangflowPage, messages: MessageRow[]) {
  await page.route(
    /\/api\/v1\/monitor\/messages(\?.*)?$/,
    async (route: Route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ json: messages });
        return;
      }

      await route.continue();
    },
  );
}

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function openMessagesRoute(
  page: LangflowPage,
  messages = populatedMessages,
) {
  await mockMessages(page, messages);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/messages");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toHaveText(
    "Messages",
    {
      timeout: TIMEOUTS.standard,
    },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

function messageRow(page: LangflowPage, text: string) {
  return page
    .locator(".ag-center-cols-container .ag-row")
    .filter({ hasText: text })
    .first();
}

test.describe("Messages settings route accessibility", () => {
  test(
    "scans the populated messages table",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      await expect(page.getByText(firstMessageText)).toBeVisible();
      await expect(
        page.getByText("The route has no automated accessibility violations."),
      ).toBeVisible();
      await expect(page.getByTestId("delete-row-button")).toBeDisabled();

      await page.runA11yScan("settings-messages-populated");
    },
  );

  test(
    "exposes one named messages grid with a roving row tab stop",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const grid = page.getByRole("treegrid", { name: "Messages" });

      await expect(grid).toBeVisible();
      await expect(
        grid.locator('.ag-center-cols-container [role="row"][tabindex="0"]'),
      ).toHaveCount(1);
      await expect(
        grid.locator(
          '[role="gridcell"][tabindex="0"], [role="columnheader"][tabindex="0"]',
        ),
      ).toHaveCount(0);
      await expect(
        grid.locator('.ag-paging-button.ag-disabled:not([tabindex="-1"])'),
      ).toHaveCount(0);
    },
  );

  test(
    "truncates message text without vertically clipping emoji",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const textTrigger = messageRow(page, firstMessageText).locator(
        '[role="gridcell"][col-id="text"] [data-langflow-text-cell-trigger]',
      );

      await expect(textTrigger).toBeVisible();
      await expect(textTrigger).toHaveAccessibleName(firstMessageText);
      await expect(textTrigger).toHaveClass(/truncate/);
      await expect
        .poll(() =>
          textTrigger.evaluate((element) => {
            const style = window.getComputedStyle(element);
            const content = element.querySelector("span");
            const triggerBounds = element.getBoundingClientRect();
            const contentBounds = content?.getBoundingClientRect();
            return {
              contentVerticallyContained: Boolean(
                contentBounds &&
                  contentBounds.top >= triggerBounds.top - 1 &&
                  contentBounds.bottom <= triggerBounds.bottom + 1,
              ),
              lineHeight: style.lineHeight,
              overflow: style.overflow,
              textOverflow: style.textOverflow,
              whiteSpace: style.whiteSpace,
            };
          }),
        )
        .toEqual({
          contentVerticallyContained: true,
          lineHeight: "24px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        });
    },
  );

  test(
    "toggles message selection with Space without opening the text viewer",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const row = messageRow(page, firstMessageText);
      const textCell = row.locator('[role="gridcell"][col-id="text"]');
      await textCell.focus();

      await page.keyboard.press(" ");
      await expect(row).toHaveAttribute("aria-selected", "true");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByTestId("delete-row-button")).toBeEnabled();

      await page.keyboard.press(" ");
      await expect(row).toHaveAttribute("aria-selected", "false");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByTestId("delete-row-button")).toBeDisabled();
    },
  );

  test(
    "leaves and re-enters the messages grid without a keyboard trap",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const row = messageRow(page, firstMessageText);
      await row.locator(".ag-selection-checkbox").click();
      const deleteButton = page.getByTestId("delete-row-button");
      await expect(deleteButton).toBeEnabled();

      const lastCell = page
        .locator(".ag-center-cols-container [role='gridcell']")
        .last();
      await lastCell.focus();
      await page.keyboard.press("Tab");
      await expect(deleteButton).toBeFocused();

      const escapedDeleteControl: boolean[] = [];
      for (let index = 0; index < 4; index += 1) {
        await page.keyboard.press("Shift+Tab");
        escapedDeleteControl.push(
          await page.evaluate(() => {
            const activeElement = document.activeElement;
            return (
              activeElement instanceof HTMLElement &&
              activeElement.tagName !== "BODY" &&
              activeElement.getAttribute("data-testid") !== "delete-row-button"
            );
          }),
        );
      }
      expect(escapedDeleteControl.some(Boolean)).toBe(true);
    },
  );

  test(
    "scans the empty messages state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page, []);
      await expect(page.getByText("No Data Available")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-messages-empty");
    },
  );

  test(
    "scans the named loading state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      let releaseResponse = () => {};
      const responseGate = new Promise<void>((resolve) => {
        releaseResponse = resolve;
      });
      await page.route(
        /\/api\/v1\/monitor\/messages(\?.*)?$/,
        async (route: Route) => {
          if (route.request().method() !== "GET") {
            await route.continue();
            return;
          }
          await responseGate;
          await route.fulfill({ json: populatedMessages });
        },
      );
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/messages");

      await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
      await page.runA11yScan("settings-messages-loading");
      releaseResponse();
    },
  );

  test(
    "scans a selected message row",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const row = messageRow(page, firstMessageText);
      await row.locator(".ag-selection-checkbox").click();
      await expect(row).toHaveAttribute("aria-selected", "true");
      await expect(page.getByTestId("delete-row-button")).toBeEnabled();

      await page.runA11yScan("settings-messages-row-selected");
    },
  );

  test(
    "scans the text viewer opened from the keyboard",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const textCell = messageRow(page, firstMessageText).locator(
        '[role="gridcell"][col-id="text"]',
      );
      await textCell.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("dialog", { name: "View Text" })).toBeVisible(
        {
          timeout: TIMEOUTS.standard,
        },
      );
      await expect(
        page.getByRole("textbox", { name: "View Text" }),
      ).toBeVisible();

      await page.runA11yScan("settings-messages-text-viewer");
    },
  );

  test(
    "restores focus to the text cell after the viewer closes",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openMessagesRoute(page);
      const textCell = messageRow(page, firstMessageText).locator(
        '[role="gridcell"][col-id="text"]',
      );
      await textCell.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("dialog", { name: "View Text" })).toBeVisible(
        {
          timeout: TIMEOUTS.standard,
        },
      );

      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect
        .poll(
          async () =>
            page.evaluate(
              () =>
                document.activeElement
                  ?.closest('[col-id="text"]')
                  ?.getAttribute("col-id") ?? "",
            ),
          { timeout: TIMEOUTS.standard },
        )
        .toBe("text");

      await page.keyboard.press("Enter");
      await expect(page.getByRole("dialog", { name: "View Text" })).toBeVisible(
        {
          timeout: TIMEOUTS.standard,
        },
      );
    },
  );

  test(
    "scans the populated messages table on mobile",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 320, height: 800 });
      await openMessagesRoute(page);
      await expect(page.getByText(firstMessageText)).toBeVisible();

      await page.runA11yScan("settings-messages-mobile");
    },
  );
});
