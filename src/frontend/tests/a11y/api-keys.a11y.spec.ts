import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type ApiKeyRow = {
  name: string;
  last_used_at: string | null;
  total_uses: number;
  is_active: boolean;
  id: string;
  api_key: string;
  user_id: string;
  created_at: string;
  expires_at: string | null;
};

const populatedApiKeys: ApiKeyRow[] = [
  {
    id: "a11y-api-key-1",
    user_id: "a11y-user",
    name: "A11y Primary Key",
    api_key: "lf-key-alpha-redacted", // pragma: allowlist secret
    created_at: "2026-06-01T12:00:00",
    last_used_at: null,
    expires_at: null,
    total_uses: 0,
    is_active: true,
  },
  {
    id: "a11y-api-key-2",
    user_id: "a11y-user",
    name: "A11y Expiring Key",
    api_key: "lf-key-beta-redacted", // pragma: allowlist secret
    created_at: "2026-06-10T12:00:00",
    last_used_at: "2026-06-20T12:00:00",
    expires_at: "2026-12-31T23:59:59",
    total_uses: 42,
    is_active: true,
  },
];

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

async function mockApiKeys(page: LangflowPage, apiKeys: ApiKeyRow[]) {
  await page.route(/\/api\/v1\/api_key\/?.*/, async (route: Route) => {
    const request = route.request();
    const method = request.method();

    if (method === "GET") {
      await route.fulfill({
        json: {
          total_count: apiKeys.length,
          user_id: "a11y-user",
          api_keys: apiKeys,
        },
      });
      return;
    }

    if (method === "POST") {
      await route.fulfill({
        json: {
          id: "a11y-generated-key",
          api_key: "lf-generated-api-key-redacted", // pragma: allowlist secret
        },
      });
      return;
    }

    if (method === "DELETE") {
      await route.fulfill({
        json: { message: "API key deleted" },
      });
      return;
    }

    await route.continue();
  });
}

async function openApiKeysRoute(
  page: LangflowPage,
  apiKeys = populatedApiKeys,
) {
  await mockApiKeys(page, apiKeys);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/api-keys");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toContainText(
    "Langflow API Keys",
    { timeout: TIMEOUTS.standard },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

type FocusableSnapshot = {
  name: string;
  role: string | null;
  tagName: string;
  testId: string | null;
  tabIndex: number;
  className: string;
};

type FocusTraversalSnapshot = FocusableSnapshot & {
  isDisabledPagingButton: boolean;
};

type ActiveElementSnapshot = FocusTraversalSnapshot & {
  colId: string | null;
  isGridCell: boolean;
  isTabGuard: boolean;
};

async function getVisibleTabOrder(page: LangflowPage) {
  return page.evaluate<FocusableSnapshot[]>(() => {
    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      '[tabindex]:not([tabindex="-1"])',
      '[contenteditable="true"]',
    ].join(",");

    const isVisibleFocusable = (element: HTMLElement) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();

      return (
        element.tabIndex >= 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rect.width > 0 &&
        rect.height > 0 &&
        !element.closest('[inert], [aria-hidden="true"]')
      );
    };

    const getName = (element: HTMLElement) =>
      (
        element.getAttribute("aria-label") ??
        element.getAttribute("title") ??
        element.innerText ??
        element.getAttribute("data-testid") ??
        element.id ??
        element.tagName
      )
        .replace(/\s+/g, " ")
        .trim();

    return Array.from(document.querySelectorAll<HTMLElement>(focusableSelector))
      .filter(isVisibleFocusable)
      .map((element) => ({
        name: getName(element),
        role: element.getAttribute("role"),
        tagName: element.tagName.toLowerCase(),
        testId: element.getAttribute("data-testid"),
        tabIndex: element.tabIndex,
        className: String(element.className),
      }));
  });
}

async function collectTabTraversal(page: LangflowPage, steps: number) {
  const focusedElements: FocusTraversalSnapshot[] = [];

  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });

  for (let index = 0; index < steps; index += 1) {
    await page.keyboard.press("Tab");
    await page.waitForTimeout(20);
    focusedElements.push(
      await page.evaluate<FocusTraversalSnapshot>(() => {
        const element = document.activeElement as HTMLElement | null;
        const getName = (activeElement: HTMLElement | null) =>
          (
            activeElement?.getAttribute("aria-label") ??
            activeElement?.getAttribute("title") ??
            activeElement?.innerText ??
            activeElement?.getAttribute("data-testid") ??
            activeElement?.id ??
            activeElement?.tagName ??
            ""
          )
            .replace(/\s+/g, " ")
            .trim();

        return {
          name: getName(element),
          role: element?.getAttribute("role") ?? null,
          tagName: element?.tagName.toLowerCase() ?? "",
          testId: element?.getAttribute("data-testid") ?? null,
          tabIndex: element?.tabIndex ?? -1,
          className: String(element?.className ?? ""),
          isDisabledPagingButton: Boolean(
            element?.closest(
              ".ag-paging-button.ag-disabled, .ag-paging-button[aria-disabled='true']",
            ),
          ),
        };
      }),
    );
  }

  return focusedElements;
}

async function getActiveElementSnapshot(page: LangflowPage) {
  return page.evaluate<ActiveElementSnapshot>(() => {
    const element = document.activeElement as HTMLElement | null;
    const getName = (activeElement: HTMLElement | null) =>
      (
        activeElement?.getAttribute("aria-label") ??
        activeElement?.getAttribute("title") ??
        activeElement?.innerText ??
        activeElement?.getAttribute("data-testid") ??
        activeElement?.id ??
        activeElement?.tagName ??
        ""
      )
        .replace(/\s+/g, " ")
        .trim();

    return {
      name: getName(element),
      role: element?.getAttribute("role") ?? null,
      tagName: element?.tagName.toLowerCase() ?? "",
      testId: element?.getAttribute("data-testid") ?? null,
      tabIndex: element?.tabIndex ?? -1,
      className: String(element?.className ?? ""),
      colId: element?.getAttribute("col-id") ?? null,
      isDisabledPagingButton: Boolean(
        element?.closest(
          ".ag-paging-button.ag-disabled, .ag-paging-button[aria-disabled='true']",
        ),
      ),
      isGridCell: element?.getAttribute("role") === "gridcell",
      isTabGuard: Boolean(element?.classList.contains("ag-tab-guard")),
    };
  });
}

test.describe("API keys route accessibility", () => {
  test(
    "scans populated API keys table",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);
      await expect(page.getByText("A11y Primary Key")).toBeVisible();
      await expect(page.getByText("A11y Expiring Key")).toBeVisible();

      await page.runA11yScan("settings-api-keys-data-rich");
    },
  );

  test(
    "keeps API keys route tab order usable",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);

      const tabOrder = await getVisibleTabOrder(page);
      const realFocusOrder = await collectTabTraversal(page, 80);
      const sidebarItems = tabOrder.filter((item) =>
        item.testId?.startsWith("sidebar-nav-"),
      );
      const rowContainers = tabOrder.filter((item) => item.role === "row");
      const disabledPagingButtons = await page.evaluate(() => {
        return Array.from(
          document.querySelectorAll<HTMLElement>(".ag-paging-button"),
        )
          .filter(
            (btn) =>
              btn.classList.contains("ag-disabled") &&
              (btn.tabIndex >= 0 ||
                !btn.hasAttribute("tabindex") ||
                btn.getAttribute("tabindex") !== "-1"),
          )
          .map((btn) => ({
            name: btn.getAttribute("aria-label") ?? btn.textContent?.trim(),
            className: btn.className,
          }));
      });

      expect(
        sidebarItems.length,
        "settings nav should have one tab stop per visible sidebar item",
      ).toBeGreaterThan(0);
      expect(
        sidebarItems.every((item) => item.testId?.startsWith("sidebar-nav-")),
        "all sidebar items should have sidebar-nav- test IDs",
      ).toBe(true);
      // The grid exposes exactly one tabbable row (the roving-tabindex grid
      // pattern IBM's aria_child_tabbable requires); the rest stay tabindex=-1.
      expect(
        rowContainers,
        "AG Grid should expose exactly one tabbable row (roving tabindex)",
      ).toHaveLength(1);
      expect(
        disabledPagingButtons,
        "disabled AG Grid paging buttons should not be tabbable",
      ).toHaveLength(0);
      expect(
        realFocusOrder.filter((item) => item.isDisabledPagingButton),
        "keyboard Tab should not focus disabled AG Grid paging buttons",
      ).toHaveLength(0);

      // AG Grid exposes the grid as a single logical tab stop via its own tab
      // guards and gives it an accessible name; the treegrid element itself is
      // not a tab stop and its rows/cells/headers must not be individual stops.
      const treegridName = await page.evaluate(
        () =>
          document
            .querySelector('[role="treegrid"]')
            ?.getAttribute("aria-label") ?? null,
      );
      expect(treegridName, "table should expose one named treegrid").toBe(
        "Langflow API Keys",
      );
      const cellAndHeaderTabStops = tabOrder.filter(
        (item) => item.role === "gridcell" || item.role === "columnheader",
      );
      expect(
        cellAndHeaderTabStops,
        "individual grid cells and headers should not be tab stops",
      ).toHaveLength(0);
    },
  );

  test(
    "opens API key name cells with Enter",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);

      const nameCell = page
        .locator('[role="gridcell"][col-id="name"]')
        .filter({ hasText: "A11y Primary Key" })
        .first();
      await expect(nameCell).toBeVisible();
      await nameCell.evaluate((element) => {
        (element as HTMLElement).focus();
      });
      await page.keyboard.press("Enter");

      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText("View Text")).toBeVisible();
      await expect(page.getByTestId("textarea")).toHaveValue(
        "A11y Primary Key",
      );
    },
  );

  test(
    "moves focus from the last API key header into the table body",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);

      const lastHeader = page.locator(
        '[role="columnheader"][col-id="total_uses"]',
      );
      await expect(lastHeader).toBeVisible();
      await lastHeader.evaluate((element) => {
        (element as HTMLElement).focus();
      });

      await page.keyboard.press("Tab");
      await page.waitForTimeout(20);

      const activeElement = await getActiveElementSnapshot(page);

      expect(activeElement.isGridCell, "focus should enter table body").toBe(
        true,
      );
      expect(activeElement.colId, "focus should start at first body cell").toBe(
        "name",
      );
    },
  );

  test(
    "exits the table with a single Tab from the last cell",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);

      // Select a row so the table's delete control (the first focusable element
      // after the grid) is enabled and can receive focus on tab-out.
      await page.locator(".ag-header-select-all").first().click();
      const deleteButton = page.getByTestId("delete-row-button");
      await expect(deleteButton).toBeEnabled();

      const lastCell = page
        .locator('[role="gridcell"][col-id="total_uses"]')
        .last();
      await expect(lastCell).toBeVisible();
      await lastCell.click();

      await page.keyboard.press("Tab");
      await page.waitForTimeout(50);

      const activeElement = await getActiveElementSnapshot(page);

      expect(activeElement.isGridCell, "focus should leave the grid body").toBe(
        false,
      );
      expect(
        activeElement.tagName,
        "a single Tab should reach the next control, not dead-stop on <body>",
      ).not.toBe("body");
      expect(
        activeElement.testId,
        "a single Tab should land on the delete control after the grid",
      ).toBe("delete-row-button");
    },
  );

  test(
    "re-enters the table on reverse tab from the delete control",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);

      await page.locator(".ag-header-select-all").first().click();
      const deleteButton = page.getByTestId("delete-row-button");
      await expect(deleteButton).toBeEnabled();

      // Tab out of the grid to the delete control the way a keyboard user would,
      // then reverse back. Reverse tabbing must move past the delete control and
      // must not trap by oscillating between it and <body> (the regression an
      // inert/disabled pagination panel caused, where every Shift+Tab bounced
      // delete <-> body and the grid became unreachable backwards).
      await page
        .locator('[role="gridcell"][col-id="total_uses"]')
        .last()
        .click();
      await page.keyboard.press("Tab");
      await page.waitForTimeout(50);
      expect((await getActiveElementSnapshot(page)).testId).toBe(
        "delete-row-button",
      );

      const escaped: boolean[] = [];
      for (let index = 0; index < 4; index += 1) {
        await page.keyboard.press("Shift+Tab");
        await page.waitForTimeout(40);
        const snapshot = await getActiveElementSnapshot(page);
        escaped.push(
          snapshot.tagName !== "body" &&
            snapshot.testId !== "delete-row-button",
        );
      }

      expect(
        escaped.some(Boolean),
        "reverse tab must progress past the delete control, not trap on delete <-> body",
      ).toBe(true);
    },
  );

  test(
    "scans empty API keys table",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page, []);
      await expect(page.getByText("No data available")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("settings-api-keys-empty");
    },
  );

  test(
    "scans create API key modal form",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);
      await page.getByTestId("api-key-button-store").click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText("Create API Key")).toBeVisible();
      await expect(page.locator("#primary-input")).toBeVisible();
      await expect(page.locator("#expires-at-input")).toBeVisible();

      await page.runA11yScan("settings-api-keys-create-modal");
    },
  );

  test(
    "scans generated API key modal state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);
      await page.getByTestId("api-key-button-store").click();
      await page.locator("#primary-input").fill("A11y generated key");
      await page.getByRole("button", { name: "1 week from today" }).click();
      await page.getByTestId("secret_key_modal_submit_button").click();
      await expect(page.getByTestId("api-key-input")).toHaveValue(
        "lf-generated-api-key-redacted",
        { timeout: TIMEOUTS.standard },
      );
      await expect(page.getByTestId("btn-copy-api-key")).toBeVisible();

      await page.runA11yScan("settings-api-keys-generated-modal");
    },
  );

  test(
    "scans API key text cell modal",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);
      await page
        .getByRole("button", { name: "A11y Primary Key", exact: true })
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText("View Text")).toBeVisible();

      await page.runA11yScan("settings-api-keys-text-cell-modal");
    },
  );

  test(
    "scans selected API key table state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openApiKeysRoute(page);
      const firstRow = page
        .locator(".ag-center-cols-container .ag-row")
        .first();
      await firstRow.locator(".ag-selection-checkbox").click();
      await expect(firstRow).toHaveAttribute("aria-selected", "true");

      await page.runA11yScan("settings-api-keys-row-selected");
    },
  );

  test(
    "scans populated API keys table on mobile width",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openApiKeysRoute(page);
      await expect(page.getByText("A11y Primary Key")).toBeVisible();
      await expect(
        page.getByTestId("sidebar-nav-Langflow API Keys"),
      ).toBeVisible();

      await page.runA11yScan("settings-api-keys-mobile-data-rich");
    },
  );
});
