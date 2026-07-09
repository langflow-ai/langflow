import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type VariableRow = {
  id: string;
  name: string;
  type: "Credential" | "Generic";
  value: string;
  default_fields: string[];
  is_valid: boolean | null;
  validation_error: string | null;
};

const populatedVariables: VariableRow[] = [
  {
    id: "a11y-variable-1",
    name: "OPENAI_API_KEY",
    type: "Credential",
    value: "sk-a11y-redacted", // pragma: allowlist secret
    default_fields: ["api_key"],
    is_valid: true,
    validation_error: null,
  },
  {
    id: "a11y-variable-2",
    name: "DEFAULT_MODEL",
    type: "Generic",
    value: "gpt-4.1-mini",
    default_fields: ["model_name"],
    is_valid: null,
    validation_error: null,
  },
];

const invalidProviderVariables: VariableRow[] = [
  {
    id: "a11y-invalid-openai",
    name: "OPENAI_API_KEY",
    type: "Credential",
    value: "sk-invalid", // pragma: allowlist secret
    default_fields: ["api_key"],
    is_valid: false,
    validation_error: "Invalid API key",
  },
  {
    id: "a11y-variable-2",
    name: "DEFAULT_MODEL",
    type: "Generic",
    value: "gpt-4.1-mini",
    default_fields: ["model_name"],
    is_valid: null,
    validation_error: null,
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

async function mockComponentTypes(page: LangflowPage) {
  // The "Apply to Fields" popover options are derived from live component
  // template data (secret fields extracted from `/api/v1/all`). Returning an
  // empty component map forces the deterministic fallback field list
  // (System / System Message / System Prompt) instead of whatever secret
  // fields happen to exist in the backend under test.
  await page.route(/\/api\/v1\/all(\?.*)?$/, async (route: Route) => {
    await route.fulfill({ json: {} });
  });
}

async function mockVariables(page: LangflowPage, variables: VariableRow[]) {
  await page.route(/\/api\/v1\/variables\/?.*/, async (route: Route) => {
    const method = route.request().method();

    if (method === "GET") {
      await route.fulfill({ json: variables });
      return;
    }

    if (method === "POST") {
      await route.fulfill({
        json: {
          id: "a11y-created-variable",
          name: "A11Y_CREATED",
          type: "Generic",
        },
      });
      return;
    }

    if (method === "PATCH") {
      await route.fulfill({
        json: {
          id: "a11y-variable-2",
          name: "DEFAULT_MODEL",
          type: "Generic",
        },
      });
      return;
    }

    if (method === "DELETE") {
      await route.fulfill({ json: { message: "Variable deleted" } });
      return;
    }

    await route.continue();
  });
}

async function openGlobalVariablesRoute(
  page: LangflowPage,
  variables = populatedVariables,
) {
  await mockVariables(page, variables);
  await mockComponentTypes(page);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/global-variables");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toContainText(
    "Global Variables",
    { timeout: TIMEOUTS.standard },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

async function openCreateModal(page: LangflowPage) {
  await page.getByTestId("api-key-button-store").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Create Variable" }),
  ).toBeVisible();
}

async function openApplyToFieldsPopover(page: LangflowPage) {
  const dialog = page.getByRole("dialog");
  await dialog.getByTestId("anchor-popover-anchor-apply-to-fields").click();
  await expect(dialog.getByPlaceholder("Fields")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

test.describe("Global variables route accessibility", () => {
  test(
    "scans populated global variables table",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await expect(page.getByText("OPENAI_API_KEY")).toBeVisible();
      await expect(page.getByText("DEFAULT_MODEL")).toBeVisible();
      await expect(page.getByText("*****")).toBeVisible();
      await expect(page.getByTestId("delete-row-button")).toBeDisabled();
      await expect(page.getByTestId("reset-columns-button")).toBeDisabled();
      await expect(
        page.getByTestId("sidebar-nav-Global Variables"),
      ).toBeVisible();

      await page.runA11yScan("settings-global-variables-data-rich");
    },
  );

  test(
    "scans empty global variables table",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page, []);
      await expect(page.getByText("No Data Available")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(
        page.getByText(
          "Oops! It seems there's no data to display right now. Please check back later.",
        ),
      ).toBeVisible();

      await page.runA11yScan("settings-global-variables-empty");
    },
  );

  test(
    "scans invalid provider credentials alert",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page, invalidProviderVariables);
      await expect(
        page.getByText("Invalid Provider Credentials Detected"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      await expect(page.getByText("DEFAULT_MODEL")).toBeVisible();
      await expect(page.getByText("OPENAI_API_KEY")).toHaveCount(0);

      await page.runA11yScan("settings-global-variables-invalid-credentials");
    },
  );

  test(
    "scans create modal credential default with disabled submit",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await expect(page.getByTestId("credential-tab")).toBeVisible();
      await expect(page.getByTestId("generic-tab")).toBeVisible();
      await expect(
        page.getByPlaceholder("Enter a name for the variable..."),
      ).toBeVisible();
      await expect(
        page.getByPlaceholder("Enter a value for the variable..."),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Show password" }),
      ).toBeVisible();
      await expect(page.getByTestId("save-variable-btn")).toBeDisabled();
      await expect(page.getByTestId("btn-cancel-modal")).toBeVisible();

      await page.runA11yScan("settings-global-variables-create-modal");
    },
  );

  test(
    "scans create modal generic type tab",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await page.getByTestId("generic-tab").click();
      await expect(page.getByTestId("generic-tab")).toHaveAttribute(
        "data-state",
        "active",
      );
      await expect(
        page.getByPlaceholder("Enter a value for the variable..."),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Show password" }),
      ).toHaveCount(0);

      await page.runA11yScan("settings-global-variables-create-modal-generic");
    },
  );

  test(
    "scans create modal with password value visible",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await page
        .getByPlaceholder("Enter a name for the variable...")
        .fill("A11Y_SECRET");
      await page
        .getByPlaceholder("Enter a value for the variable...")
        .fill("super-secret-value"); // pragma: allowlist secret
      await page.getByRole("button", { name: "Show password" }).click();
      await expect(
        page.getByRole("button", { name: "Hide password" }),
      ).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByTestId("save-variable-btn")).toBeEnabled();

      await page.runA11yScan(
        "settings-global-variables-create-modal-password-visible",
      );
    },
  );

  test(
    "scans create modal apply-to-fields popover open",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await openApplyToFieldsPopover(page);
      await expect(
        page.getByRole("dialog").getByText("System", { exact: true }).first(),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await page.runA11yScan(
        "settings-global-variables-create-modal-apply-fields-open",
      );
    },
  );

  test(
    "scans create modal with apply-to-fields selected",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await openApplyToFieldsPopover(page);
      await page
        .getByRole("dialog")
        .locator('[cmdk-item]:has-text("System")')
        .first()
        .click();
      await expect(page.getByTestId("remove-icon-badge")).toBeVisible();
      await expect(
        page.getByText(
          "Selected fields will auto-apply the variable as a default value.",
        ),
      ).toBeVisible();

      await page.runA11yScan(
        "settings-global-variables-create-modal-apply-fields-selected",
      );
    },
  );

  test(
    "scans page after create modal closes",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await openCreateModal(page);
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByTestId("api-key-button-store")).toBeVisible();
      await expect(page.getByText("OPENAI_API_KEY")).toBeVisible();

      await page.runA11yScan("settings-global-variables-modal-closed");
    },
  );

  test(
    "scans edit generic variable modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await page.locator('.ag-cell:has-text("DEFAULT_MODEL")').first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Update Variable" }),
      ).toBeVisible();
      await expect(page.getByTestId("save-variable-btn")).toBeVisible();
      // The active type's tab stays enabled/tabbable (so a tablist always has
      // at least one reachable tab); only the inactive type is locked.
      await expect(page.getByTestId("credential-tab")).toBeDisabled();
      await expect(page.getByTestId("generic-tab")).toBeEnabled();
      await expect(
        page.getByPlaceholder("Enter a name for the variable..."),
      ).toHaveValue("DEFAULT_MODEL");
      await expect(
        page.getByRole("button", { name: "Show password" }),
      ).toHaveCount(0);

      await page.runA11yScan("settings-global-variables-edit-modal");
    },
  );

  test(
    "scans edit credential variable modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await page.locator('.ag-cell:has-text("OPENAI_API_KEY")').first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Update Variable" }),
      ).toBeVisible();
      await expect(page.getByTestId("credential-tab")).toBeEnabled();
      await expect(page.getByTestId("generic-tab")).toBeDisabled();
      await expect(
        page.getByRole("button", { name: "Show password" }),
      ).toBeVisible();
      await expect(page.getByTestId("save-variable-btn")).toBeEnabled();
      await expect(page.getByTestId("remove-icon-badge")).toBeVisible();

      await page.runA11yScan("settings-global-variables-edit-modal-credential");
    },
  );

  test(
    "scans edit modal apply-to-fields popover open",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      await page.locator('.ag-cell:has-text("DEFAULT_MODEL")').first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await openApplyToFieldsPopover(page);
      await expect(
        page.getByRole("dialog").getByPlaceholder("Fields"),
      ).toBeVisible();

      await page.runA11yScan(
        "settings-global-variables-edit-modal-apply-fields-open",
      );
    },
  );

  test(
    "scans selected row with delete enabled",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      const firstRow = page
        .locator(".ag-center-cols-container .ag-row")
        .first();
      await firstRow.locator(".ag-selection-checkbox").click();
      await expect(firstRow).toHaveAttribute("aria-selected", "true");
      await expect(page.getByTestId("delete-row-button")).toBeEnabled();

      await page.runA11yScan("settings-global-variables-row-selected");
    },
  );

  test(
    "scans multi-row selected table state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openGlobalVariablesRoute(page);
      const rows = page.locator(".ag-center-cols-container .ag-row");
      await rows.nth(0).locator(".ag-selection-checkbox").click();
      await rows.nth(1).locator(".ag-selection-checkbox").click();
      await expect(rows.nth(0)).toHaveAttribute("aria-selected", "true");
      await expect(rows.nth(1)).toHaveAttribute("aria-selected", "true");
      await expect(page.getByTestId("delete-row-button")).toBeEnabled();

      await page.runA11yScan("settings-global-variables-multi-row-selected");
    },
  );
});
