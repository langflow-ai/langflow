import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  DEPLOYMENT,
  DEPLOYMENTS_MOCK,
  PROVIDERS_MOCK,
} from "../../utils/deployment-mocks";

async function navigateToDeploymentsTab(
  page: Parameters<typeof test>[2]["page"],
) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.getByTestId("deployments-btn").click();
  await page.waitForSelector('[data-testid="subtab-deployments"]');
}

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
    await page.waitForSelector('[data-testid="subtab-deployments"]');

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
    await page.waitForSelector('[data-testid="subtab-deployments"]');

    await expect(page.getByTestId("create-deployment-empty-btn")).toBeVisible();
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
    await page.waitForSelector('[data-testid="subtab-deployments"]');

    await page.getByTestId("subtab-providers").click();

    await expect(page.getByTestId("add-provider-empty-btn")).toBeVisible();
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
    await page.waitForSelector('[data-testid="subtab-deployments"]');

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
    await page.waitForSelector('[data-testid="subtab-deployments"]');

    await page.getByTestId("subtab-providers").click();

    await expect(page.getByTestId("provider-row-prov-1")).toBeVisible();
  },
);

test(
  "Delete deployment opens type-to-confirm dialog",
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
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await navigateToDeploymentsTab(page);
    await expect(page.getByTestId("deployment-row-dep-1")).toBeVisible();

    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByTestId("delete-deployment-dep-1").click();

    await expect(
      page.getByTestId("input-type-to-confirm-delete"),
    ).toBeVisible();
  },
);

test(
  "Delete deployment button is disabled until deployment name is typed",
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
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await navigateToDeploymentsTab(page);
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByTestId("delete-deployment-dep-1").click();

    const deleteBtn = page.getByTestId("btn-delete-type-to-confirm-delete");
    await expect(deleteBtn).toBeDisabled();

    await page.getByTestId("input-type-to-confirm-delete").fill("wrong name");
    await expect(deleteBtn).toBeDisabled();

    await page
      .getByTestId("input-type-to-confirm-delete")
      .fill(DEPLOYMENT.name);
    await expect(deleteBtn).toBeEnabled();
  },
);

test(
  "Delete deployment — typing correct name and confirming calls DELETE",
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
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments/dep-1", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await navigateToDeploymentsTab(page);
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByTestId("delete-deployment-dep-1").click();

    await page
      .getByTestId("input-type-to-confirm-delete")
      .fill(DEPLOYMENT.name);

    const deleteRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/dep-1") &&
        req.method() === "DELETE",
    );

    await page.getByTestId("btn-delete-type-to-confirm-delete").click();

    await deleteRequest;
  },
);

test(
  "Cancel delete deployment dismisses dialog without calling DELETE",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let deleteRequestCount = 0;

    await page.route("**/api/v1/deployments/providers*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    });

    await page.route("**/api/v1/deployments/dep-1", (route) => {
      if (route.request().method() === "DELETE") {
        deleteRequestCount++;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "{}",
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/v1/deployments*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEPLOYMENTS_MOCK),
      });
    });

    await navigateToDeploymentsTab(page);
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByTestId("delete-deployment-dep-1").click();

    await expect(
      page.getByTestId("btn-cancel-type-to-confirm-delete"),
    ).toBeVisible();

    await page.getByTestId("btn-cancel-type-to-confirm-delete").click();

    await expect(
      page.getByTestId("btn-cancel-type-to-confirm-delete"),
    ).not.toBeVisible();

    expect(deleteRequestCount).toBe(0);
    await expect(page.getByTestId("deployment-row-dep-1")).toBeVisible();
  },
);
