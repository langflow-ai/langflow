import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  ATTACHMENTS_MOCK,
  DEPLOYMENT_DETAIL_MOCK,
  DEPLOYMENTS_MOCK,
  LLMS_MOCK,
  PROVIDERS_MOCK,
} from "../../utils/deployment-mocks";

async function setupRoutes(page: Parameters<typeof test>[2]["page"]) {
  // Register broad catch-all FIRST so specific routes (registered after) take priority via LIFO
  await page.route("**/api/v1/deployments*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(DEPLOYMENTS_MOCK),
    });
  });

  await page.route("**/api/v1/deployments/configs*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configs: [], page: 1, size: 10000, total: 0 }),
    });
  });

  await page.route("**/api/v1/deployments/llms*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LLMS_MOCK),
    });
  });

  await page.route("**/api/v1/deployments/providers*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PROVIDERS_MOCK),
    });
  });

  await page.route("**/api/v1/deployments/dep-1", (route) => {
    if (route.request().method() === "PATCH") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    } else {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEPLOYMENT_DETAIL_MOCK),
      });
    }
  });

  await page.route("**/api/v1/deployments/dep-1/flows*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ATTACHMENTS_MOCK),
    });
  });
}

async function navigateToDeployments(page: Parameters<typeof test>[2]["page"]) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.getByTestId("deployments-btn").click();
  await page.waitForSelector('[data-testid="new-deployment-btn"]');
}

async function openEditDialog(page: Parameters<typeof test>[2]["page"]) {
  await page.getByTestId("actions-deployment-dep-1").click();
  await page.getByRole("menuitem", { name: "Update" }).click();
  await page.waitForSelector('[data-testid="stepper-modal-title"]');
}

test(
  "Opens edit stepper from actions menu",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupRoutes(page);
    await navigateToDeployments(page);

    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByRole("menuitem", { name: "Update" }).click();

    await page.waitForSelector('[data-testid="stepper-modal-title"]');

    await expect(page.getByTestId("stepper-modal-title")).toBeVisible();
    await expect(page.getByTestId("deployment-stepper-next")).toBeVisible();
  },
);

test(
  "Edit mode skips provider step — starts at Type",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupRoutes(page);
    await navigateToDeployments(page);

    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await openEditDialog(page);

    // Wait for stepper body to render (parallel fetches must complete)
    await page.waitForSelector('h2:has-text("Deployment Type")');

    await expect(page.getByText("Deployment Type")).toBeVisible();

    // Provider step heading should NOT be visible
    await expect(page.getByText("Choose Provider")).not.toBeVisible();

    // Navigation buttons should be present
    await expect(page.getByTestId("deployment-stepper-next")).toBeVisible();
    await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
  },
);

test(
  "Name field pre-populated in edit mode",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupRoutes(page);
    await navigateToDeployments(page);

    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await openEditDialog(page);

    // Wait for stepper body to render
    await page.waitForSelector('h2:has-text("Deployment Type")');

    const nameInput = page.getByPlaceholder("e.g., Sales Bot");
    await expect(nameInput).toHaveValue("Test Deployment");
  },
);

test(
  "Submitting PATCH closes modal",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupRoutes(page);
    await navigateToDeployments(page);

    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await openEditDialog(page);

    // Wait for stepper body to render (parallel fetches must complete)
    await page.waitForSelector('h2:has-text("Deployment Type")');

    // Navigate through the stepper steps to reach Review
    // Step: Type → click Next
    await page.getByTestId("deployment-stepper-next").click();

    // Step: Attach Flows → click Next
    await page.getByTestId("deployment-stepper-next").click();

    // Step: Review → click Update (final step)
    const patchRequestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/dep-1") &&
        req.method() === "PATCH",
    );

    await page.getByTestId("deployment-stepper-next").click();

    await patchRequestPromise;

    // Modal should close after PATCH
    await expect(page.getByTestId("stepper-modal-title")).not.toBeVisible();
  },
);

test(
  "Cancel during edit closes modal without calling PATCH",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupRoutes(page);
    await navigateToDeployments(page);

    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await openEditDialog(page);

    // Wait for stepper body to render
    await page.waitForSelector('h2:has-text("Deployment Type")');

    let patchCalled = false;
    page.on("request", (req) => {
      if (
        req.url().includes("/api/v1/deployments/dep-1") &&
        req.method() === "PATCH"
      ) {
        patchCalled = true;
      }
    });

    // Click Cancel
    await page.getByRole("button", { name: "Cancel" }).click();

    // Modal should be closed
    await expect(page.getByTestId("stepper-modal-title")).not.toBeVisible();

    // PATCH must not have been called
    expect(patchCalled).toBe(false);
  },
);
