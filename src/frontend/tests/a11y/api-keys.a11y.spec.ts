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
