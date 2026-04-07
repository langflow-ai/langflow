import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { DEPLOYMENTS_MOCK, PROVIDERS_MOCK } from "../../utils/deployment-mocks";

test(
  "Renders Deployments tab with sub-tab toggles",
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
        body: JSON.stringify({ provider_accounts: [] }),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="new-deployment-btn"]');

    await expect(page.getByTestId("subtab-deployments")).toBeVisible();
    await expect(page.getByTestId("subtab-providers")).toBeVisible();
  },
);

test(
  "Deployments empty state shows create button when no providers exist",
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
        body: JSON.stringify({ provider_accounts: [] }),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="new-deployment-btn"]');

    await expect(page.getByTestId("create-deployment-empty-btn")).toBeVisible();
    await expect(page.getByTestId("new-deployment-btn")).toBeVisible();
  },
);

test(
  "Providers empty state shows add provider button when switching to providers tab",
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
        body: JSON.stringify({ provider_accounts: [] }),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ deployments: [] }),
      });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="new-deployment-btn"]');

    await page.getByTestId("subtab-providers").click();

    await expect(page.getByTestId("add-provider-empty-btn")).toBeVisible();
    await expect(page.getByTestId("new-provider-btn")).toBeVisible();
  },
);

test(
  "Deployment list renders a row for each deployment",
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
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="new-deployment-btn"]');

    await expect(page.getByTestId("deployment-row-dep-1")).toBeVisible();
  },
);

test(
  "Provider list renders a row for each provider",
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
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="new-deployment-btn"]');

    await page.getByTestId("subtab-providers").click();

    await expect(page.getByTestId("provider-row-prov-1")).toBeVisible();
  },
);
