import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  EMPTY_PROVIDERS_MOCK,
  NEW_PROVIDER,
  PROVIDERS_MOCK,
} from "../../utils/deployment-mocks";

async function navigateToProvidersTab(
  page: Parameters<typeof test>[2]["page"],
) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.getByTestId("deployments-btn").click();
  await page.waitForSelector('[data-testid="subtab-deployments"]');
  await page.getByTestId("subtab-providers").click();
}

test(
  "Empty state shows Add Environment button",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(EMPTY_PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await navigateToProvidersTab(page);

    await expect(page.getByTestId("add-provider-empty-btn")).toBeVisible();
  },
);

test(
  "New Environment button opens modal with save disabled on empty form",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(EMPTY_PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await navigateToProvidersTab(page);

    await page.getByTestId("add-provider-empty-btn").click();

    await expect(page.getByTestId("add-provider-modal-title")).toBeVisible();
    await expect(page.getByTestId("add-provider-save")).toBeDisabled();
  },
);

test(
  "Save button becomes enabled after filling all required fields",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(EMPTY_PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await navigateToProvidersTab(page);

    await page.getByTestId("add-provider-empty-btn").click();

    await expect(page.getByTestId("add-provider-save")).toBeDisabled();

    await page.getByPlaceholder("e.g. Production").fill("My Env");
    await page
      .getByPlaceholder("Enter your API key")
      .fill("test-api-key-12345");
    await page
      .getByPlaceholder("https://api.example.com")
      .fill("https://example.com");

    await expect(page.getByTestId("add-provider-save")).toBeEnabled();
  },
);

test(
  "Save calls POST and modal closes",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let postCalled = false;

    await page.route("**/api/v1/deployments/providers*", (route) => {
      const method = route.request().method();

      if (method === "POST") {
        postCalled = true;
        route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(NEW_PROVIDER),
        });
      } else {
        const body = postCalled
          ? { provider_accounts: [NEW_PROVIDER] }
          : EMPTY_PROVIDERS_MOCK;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(body),
        });
      }
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await navigateToProvidersTab(page);

    await page.getByTestId("add-provider-empty-btn").click();

    await page.getByPlaceholder("e.g. Production").fill("My Env");
    await page
      .getByPlaceholder("Enter your API key")
      .fill("test-api-key-12345");
    await page
      .getByPlaceholder("https://api.example.com")
      .fill("https://example.com");

    const postRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/providers") &&
        req.method() === "POST",
    );

    await page.getByTestId("add-provider-save").click();

    await postRequest;

    await expect(
      page.getByTestId("add-provider-modal-title"),
    ).not.toBeVisible();
  },
);

test(
  "Delete triggers confirmation dialog then calls DELETE",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await page.route("**/api/v1/deployments/providers/prov-1", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    await page.route("**/api/v1/deployments/providers*", (route) => {
      const method = route.request().method();
      if (method === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(PROVIDERS_MOCK),
        });
      } else {
        route.continue();
      }
    });

    await navigateToProvidersTab(page);

    await expect(page.getByTestId("provider-row-prov-1")).toBeVisible();

    await page.getByTestId("actions-provider-prov-1").click();
    await page.getByText("Delete").click();

    await expect(
      page.getByTestId("btn_delete_delete_confirmation_modal"),
    ).toBeVisible();

    const deleteRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/providers/prov-1") &&
        req.method() === "DELETE",
    );

    await page.getByTestId("btn_delete_delete_confirmation_modal").click();

    await deleteRequest;
  },
);

test(
  "Cancel delete dismisses confirmation without calling DELETE",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let deleteRequestCount = 0;

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await page.route("**/api/v1/deployments/providers/prov-1", (route) => {
      deleteRequestCount++;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await navigateToProvidersTab(page);

    await expect(page.getByTestId("provider-row-prov-1")).toBeVisible();

    await page.getByTestId("actions-provider-prov-1").click();
    await page.getByText("Delete").click();

    await expect(
      page.getByTestId("btn_cancel_delete_confirmation_modal"),
    ).toBeVisible();

    await page.getByTestId("btn_cancel_delete_confirmation_modal").click();

    await expect(
      page.getByTestId("btn_cancel_delete_confirmation_modal"),
    ).not.toBeVisible();

    expect(deleteRequestCount).toBe(0);

    await expect(page.getByTestId("provider-row-prov-1")).toBeVisible();
  },
);
