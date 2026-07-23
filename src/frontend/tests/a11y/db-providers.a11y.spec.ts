import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type GlobalVariableFixture = {
  id: string;
  type: "Credential" | "Generic";
  default_fields: string[];
  name: string;
  value?: string;
};

type WriteBehavior = {
  delayMs?: number;
  fail?: boolean;
};

type TestConnectionBehavior = {
  delayMs?: number;
  response?: { ok: boolean; message: string };
};

const emptyVariables: GlobalVariableFixture[] = [];

const openSearchConfiguredVariables: GlobalVariableFixture[] = [
  {
    id: "a11y-active-provider",
    type: "Generic",
    default_fields: [],
    name: "LANGFLOW_KNOWLEDGE_BACKEND",
    value: "opensearch",
  },
  {
    id: "a11y-os-url",
    type: "Generic",
    default_fields: [],
    name: "OPENSEARCH_URL",
    value: "https://search.example.com:9200",
  },
  {
    id: "a11y-os-username",
    type: "Generic",
    default_fields: [],
    name: "OPENSEARCH_USERNAME",
    value: "admin",
  },
  {
    id: "a11y-os-index-name",
    type: "Generic",
    default_fields: [],
    name: "OPENSEARCH_INDEX_NAME",
    value: "langflow_knowledge",
  },
  {
    // Credential-type variables are masked server-side — value is
    // intentionally omitted here to mirror the real API response.
    id: "a11y-os-password",
    type: "Credential",
    default_fields: [],
    name: "OPENSEARCH_PASSWORD", // pragma: allowlist secret
  },
  {
    id: "a11y-os-use-ssl",
    type: "Generic",
    default_fields: [],
    name: "OPENSEARCH_USE_SSL",
    value: "false",
  },
  {
    id: "a11y-os-verify-certs",
    type: "Generic",
    default_fields: [],
    name: "OPENSEARCH_VERIFY_CERTS", // pragma: allowlist secret
    value: "false",
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

async function mockGlobalVariables(
  page: LangflowPage,
  variables: GlobalVariableFixture[],
  writeBehavior: WriteBehavior = {},
) {
  await page.route(/\/api\/v1\/variables\/?.*/, async (route: Route) => {
    const request = route.request();
    const method = request.method();

    if (method === "GET") {
      await route.fulfill({ json: variables });
      return;
    }

    if (method === "POST" || method === "PATCH") {
      if (writeBehavior.delayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, writeBehavior.delayMs),
        );
      }

      if (writeBehavior.fail) {
        await route.fulfill({
          status: 500,
          json: {
            detail: "Simulated write failure for accessibility testing.",
          },
        });
        return;
      }

      const body = (request.postDataJSON() as Record<string, unknown>) ?? {};
      await route.fulfill({
        json: {
          id: (body.id as string) ?? "a11y-db-provider-variable",
          name: body.name ?? "a11y-db-provider-variable",
          type: body.type ?? "Generic",
        },
      });
      return;
    }

    await route.continue();
  });
}

async function mockTestConnection(
  page: LangflowPage,
  behavior: TestConnectionBehavior,
) {
  await page.route(
    /\/api\/v1\/knowledge_bases\/test-connection.*/,
    async (route: Route) => {
      if (behavior.delayMs) {
        await new Promise((resolve) => setTimeout(resolve, behavior.delayMs));
      }
      await route.fulfill({
        json: behavior.response ?? { ok: true, message: "" },
      });
    },
  );
}

async function openDbProvidersRoute(
  page: LangflowPage,
  variables: GlobalVariableFixture[] = emptyVariables,
  writeBehavior: WriteBehavior = {},
) {
  await mockGlobalVariables(page, variables, writeBehavior);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/db-providers");
  await disableAnimations(page);
  await expect(page.getByTestId("settings_menu_header")).toContainText(
    "DB Providers",
    { timeout: TIMEOUTS.standard },
  );
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

test.describe("DB providers route accessibility", () => {
  test(
    "scans default Chroma Local active state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);
      await expect(page.getByTestId("db-provider-item-chroma")).toBeVisible();
      await expect(
        page.getByTestId("db-provider-item-chroma").getByText("Active"),
      ).toBeVisible();

      await page.runA11yScan("db-providers-chroma-default");
    },
  );

  test(
    "scans Chroma Cloud unconfigured configuration form",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);
      await page.getByTestId("db-provider-item-chroma_cloud").click();

      await expect(page.getByLabel("API Key")).toBeVisible();
      await expect(page.getByLabel("Tenant")).toBeVisible();
      await expect(page.getByLabel("Database")).toBeVisible();
      await expect(page.getByLabel("Region")).toBeVisible();
      // Required "API Key" is empty, so both actions must be disabled —
      // asserting this exercises the `disabled` path on real <button>s
      // rather than just their presence.
      await expect(
        page.getByTestId("db-provider-test-connection"),
      ).toBeDisabled();
      await expect(
        page.getByRole("button").filter({ hasText: "Save and use" }),
      ).toBeDisabled();

      await page.runA11yScan("db-providers-chroma-cloud-form");
    },
  );

  test(
    "scans OpenSearch unconfigured configuration form with default toggle states",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);
      await page.getByTestId("db-provider-item-opensearch").click();

      await expect(page.getByLabel("Cluster URL")).toBeVisible();
      await expect(page.getByLabel("Username")).toBeVisible();
      await expect(page.getByLabel("Password")).toBeVisible();
      await expect(page.getByLabel("Default index name")).toBeVisible();
      await expect(page.getByLabel("Vector field")).toBeVisible();
      await expect(page.getByLabel("Text field")).toBeVisible();

      const useSslToggle = page.getByTestId(
        "db-provider-toggle-OPENSEARCH_USE_SSL",
      );
      const verifyCertsToggle = page.getByTestId(
        "db-provider-toggle-OPENSEARCH_VERIFY_CERTS", // pragma: allowlist secret
      );
      await expect(useSslToggle).toHaveAttribute("data-state", "checked");
      await expect(verifyCertsToggle).toHaveAttribute("data-state", "checked");
      // Required Cluster URL/Username/Password/Index name are empty, so
      // both actions must be disabled.
      await expect(
        page.getByTestId("db-provider-test-connection"),
      ).toBeDisabled();
      await expect(
        page.getByRole("button").filter({ hasText: "Save and use" }),
      ).toBeDisabled();

      await page.runA11yScan("db-providers-opensearch-form");
    },
  );

  test(
    "scans OpenSearch form with TLS toggles switched off",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);
      await page.getByTestId("db-provider-item-opensearch").click();

      const useSslToggle = page.getByTestId(
        "db-provider-toggle-OPENSEARCH_USE_SSL",
      );
      const verifyCertsToggle = page.getByTestId(
        "db-provider-toggle-OPENSEARCH_VERIFY_CERTS", // pragma: allowlist secret
      );
      await useSslToggle.click();
      await verifyCertsToggle.click();
      await expect(useSslToggle).toHaveAttribute("data-state", "unchecked");
      await expect(verifyCertsToggle).toHaveAttribute(
        "data-state",
        "unchecked",
      );

      await page.runA11yScan("db-providers-opensearch-toggles-off");
    },
  );

  test(
    "scans OpenSearch configured/active state with masked secret field",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, openSearchConfiguredVariables);

      await expect(
        page.getByTestId("db-provider-item-opensearch").getByText("Active"),
      ).toBeVisible();
      await expect(page.getByLabel("Password")).toHaveValue("••••••••");
      await expect(page.getByLabel("Cluster URL")).toHaveValue(
        "https://search.example.com:9200",
      );

      await page.runA11yScan("db-providers-opensearch-configured-masked");
    },
  );

  test(
    "scans secret field editing/unmasked state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, openSearchConfiguredVariables);

      const passwordField = page.getByLabel("Password");
      await expect(passwordField).toHaveValue("••••••••");
      await passwordField.click();
      await expect(passwordField).toHaveValue("");

      await page.runA11yScan("db-providers-opensearch-secret-editing");
    },
  );

  test(
    "scans coming-soon provider panel",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);

      // All three stubbed providers share the same coming-soon render
      // path; assert each of their list buttons individually so every
      // provider button in the list is exercised at least once, not just
      // the one whose panel we scan below.
      for (const providerId of ["astra", "mongodb", "postgres"]) {
        await expect(
          page
            .getByTestId(`db-provider-item-${providerId}`)
            .getByText("Coming soon"),
        ).toBeVisible();
      }

      await page.getByTestId("db-provider-item-astra").click();
      await expect(
        page.getByText(
          "This provider is stubbed in the Knowledge Base backend registry",
        ),
      ).toBeVisible();

      await page.runA11yScan("db-providers-coming-soon");
    },
  );

  test(
    "scans save-pending loading state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      // Chroma Local's "Use Chroma" action fires a single activation
      // request (no preceding field-save call), so delaying it produces a
      // stable, gap-free pending window to scan — unlike the two-phase
      // save-then-activate flow used by the other providers.
      const writeBehavior: WriteBehavior = {};
      await openDbProvidersRoute(
        page,
        openSearchConfiguredVariables,
        writeBehavior,
      );
      // Locate by text content rather than accessible role name: the
      // Button component visually hides its label (CSS `invisible`) while
      // `loading` is true, which strips the accessible name from the a11y
      // tree — a real gap this scan is designed to surface — so a
      // name-based role query would stop matching mid-flight.
      await page.getByTestId("db-provider-item-chroma").click();
      const useChromaButton = page
        .getByRole("button")
        .filter({ hasText: "Use Chroma" });
      await expect(useChromaButton).toBeEnabled();

      writeBehavior.delayMs = 1500;
      await useChromaButton.click();
      // Busy uses aria-disabled (not native disabled) so focus is retained.
      await expect(useChromaButton).toHaveAttribute("aria-busy", "true");
      await expect(useChromaButton).toHaveAttribute("aria-disabled", "true");

      await page.runA11yScan("db-providers-save-pending");
    },
  );

  test(
    "scans save success toast state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, emptyVariables);
      await page.getByTestId("db-provider-item-chroma_cloud").click();
      await page.getByLabel("API Key").fill("ck-a11y-test-key");
      await page
        .getByRole("button", { name: "Save and use Chroma Cloud" })
        .click();

      await expect(
        page.getByText("Chroma Cloud configuration saved"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await page.runA11yScan("db-providers-save-success");
    },
  );

  test(
    "scans save error toast state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      const writeBehavior: WriteBehavior = { fail: true };
      await openDbProvidersRoute(page, emptyVariables, writeBehavior);
      await page.getByTestId("db-provider-item-chroma_cloud").click();
      await page.getByLabel("API Key").fill("ck-a11y-test-key");
      await page
        .getByRole("button", { name: "Save and use Chroma Cloud" })
        .click();

      await expect(page.getByText("Error saving DB Provider")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("db-providers-save-error");
    },
  );

  test(
    "scans test-connection pending loading state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      const testConnectionBehavior: TestConnectionBehavior = {
        delayMs: 1500,
        response: { ok: true, message: "" },
      };
      await openDbProvidersRoute(page, openSearchConfiguredVariables);
      await mockTestConnection(page, testConnectionBehavior);

      const testConnectionButton = page.getByTestId(
        "db-provider-test-connection",
      );
      await testConnectionButton.focus();
      await testConnectionButton.press("Enter");
      // Busy uses aria-disabled (not native disabled) so focus is retained.
      await expect(testConnectionButton).toHaveAttribute("aria-busy", "true");
      await expect(testConnectionButton).toHaveAttribute(
        "aria-disabled",
        "true",
      );
      await expect(testConnectionButton).toBeFocused();

      await page.runA11yScan("db-providers-test-connection-pending");
    },
  );

  test(
    "retains keyboard focus on test-connection after loading completes",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      const testConnectionBehavior: TestConnectionBehavior = {
        delayMs: 400,
        response: { ok: false, message: "Authentication failed." },
      };
      await openDbProvidersRoute(page, openSearchConfiguredVariables);
      await mockTestConnection(page, testConnectionBehavior);

      const testConnectionButton = page.getByTestId(
        "db-provider-test-connection",
      );
      await testConnectionButton.focus();
      await expect(testConnectionButton).toBeFocused();
      await testConnectionButton.press("Enter");

      await expect(testConnectionButton).toHaveAttribute("aria-busy", "true");
      await expect(testConnectionButton).toBeFocused();

      await expect(page.getByText("Connection failed")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(testConnectionButton).not.toHaveAttribute("aria-busy");
      await expect(testConnectionButton).toBeFocused();
    },
  );

  test(
    "scans test-connection success toast state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, openSearchConfiguredVariables);
      await mockTestConnection(page, {
        response: { ok: true, message: "cluster v2.11.0" },
      });

      await page.getByTestId("db-provider-test-connection").click();
      await expect(
        page.getByText("Connection successful — cluster v2.11.0"),
      ).toBeVisible({ timeout: TIMEOUTS.standard });

      await page.runA11yScan("db-providers-test-connection-success");
    },
  );

  test(
    "scans test-connection failure toast state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await openDbProvidersRoute(page, openSearchConfiguredVariables);
      await mockTestConnection(page, {
        response: { ok: false, message: "Authentication failed." },
      });

      await page.getByTestId("db-provider-test-connection").click();
      await expect(page.getByText("Connection failed")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByText("Authentication failed.")).toBeVisible();

      await page.runA11yScan("db-providers-test-connection-failure");
    },
  );
});
