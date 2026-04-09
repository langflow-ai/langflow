import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  ATTACHMENTS_MOCK,
  ATTACHMENTS_WITH_CONNECTIONS_MOCK,
  CONFIGS_WITH_CONNECTIONS_MOCK,
  DEPLOYMENT_DETAIL_MOCK,
  DEPLOYMENTS_MOCK,
  FLOW_VERSIONS_MOCK,
  FLOWS_MOCK,
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
  await page.waitForSelector('[data-testid="subtab-deployments"]');
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

// ---------------------------------------------------------------------------
// Helper: set up routes with connection data for edit-mode connection tests
// ---------------------------------------------------------------------------
async function setupRoutesWithConnections(
  page: Parameters<typeof test>[2]["page"],
  folderId: string,
) {
  // Broad catch-all FIRST
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
      body: JSON.stringify(CONFIGS_WITH_CONNECTIONS_MOCK),
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

  // Attachments with provider_data containing app_ids
  await page.route("**/api/v1/deployments/dep-1/flows*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ATTACHMENTS_WITH_CONNECTIONS_MOCK),
    });
  });

  // Flows list
  await page.route("**/api/v1/flows/**", (route) => {
    const url = route.request().url();
    if (url.includes("/versions/")) {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FLOW_VERSIONS_MOCK),
      });
      return;
    }
    const flows = FLOWS_MOCK.map((f) => ({ ...f, folder_id: folderId }));
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(flows),
    });
  });

  // Global variables
  await page.route("**/api/v1/variables**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Env var detection
  await page.route("**/api/v1/variables/detections**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ variables: [] }),
    });
  });
}

// ---------------------------------------------------------------------------
// Test: PATCH includes new connections added to a pre-existing flow
// ---------------------------------------------------------------------------
test(
  "Edit mode includes new connections in PATCH request",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    // Capture folder ID from the projects API before bootstrap
    const projectsResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/projects") && resp.status() === 200,
      { timeout: 30000 },
    );

    await awaitBootstrapTest(page, { skipModal: true });

    let folderId = "";
    try {
      const projectsResp = await projectsResponsePromise;
      const folders = await projectsResp.json();
      const match = Array.isArray(folders)
        ? (folders.find(
            (f: { name: string; id: string }) => f.name === "Starter Project",
          ) ?? folders[0])
        : null;
      folderId = (match as { id: string } | null)?.id ?? "";
    } catch {
      // proceed
    }

    await setupRoutesWithConnections(page, folderId);
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="subtab-deployments"]');

    // Open edit dialog
    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByRole("menuitem", { name: "Update" }).click();
    await page.waitForSelector('[data-testid="stepper-modal-title"]');

    // Step 1 (Type) → Next
    await page.waitForSelector('h2:has-text("Deployment Type")');
    await page.getByTestId("deployment-stepper-next").click();

    // Step 2 (Attach Flows) — flow "f1" should already be attached
    await page.waitForSelector("text=Attach Flows");
    await page.waitForSelector('[data-testid="flow-item-f1"]');

    // Click the pre-attached flow and its version to open the connection panel
    await page.getByTestId("flow-item-f1").click();
    await page.waitForSelector('[data-testid="version-item-fv1"]');
    await page.getByTestId("version-item-fv1").click();

    // Wait for connection panel to appear with available connections
    await page.waitForSelector('[data-testid="connection-item-existing-app"]');
    await page.waitForSelector('[data-testid="connection-item-new-app"]');

    // The existing connection should already be checked; select the new one too
    await page.getByTestId("connection-item-new-app").click();

    // Attach connections
    await page.getByTestId("connection-attach").click();

    // Step 3 (Review) → click Next
    await page.getByTestId("deployment-stepper-next").click();

    // Intercept the PATCH request and verify its body
    const patchRequestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/dep-1") &&
        req.method() === "PATCH",
    );

    // Click Update
    await page.getByTestId("deployment-stepper-next").click();
    const patchRequest = await patchRequestPromise;
    const body = patchRequest.postDataJSON();

    // Verify the PATCH body includes the new connection
    const upsertFlows = body?.provider_data?.upsert_flows ?? [];
    const flowEntry = upsertFlows.find(
      (f: { flow_version_id: string }) => f.flow_version_id === "fv1",
    );
    expect(flowEntry).toBeDefined();
    expect(flowEntry.add_app_ids).toContain("new-app");
    // The existing connection should NOT appear in add_app_ids (it was already there)
    expect(flowEntry.add_app_ids).not.toContain("existing-app");
    // Nothing was removed
    expect(flowEntry.remove_app_ids).toEqual([]);
  },
);

// ---------------------------------------------------------------------------
// Test: PATCH includes removed connections from a pre-existing flow
// ---------------------------------------------------------------------------
test(
  "Edit mode includes removed connections in PATCH request",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    const projectsResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/projects") && resp.status() === 200,
      { timeout: 30000 },
    );

    await awaitBootstrapTest(page, { skipModal: true });

    let folderId = "";
    try {
      const projectsResp = await projectsResponsePromise;
      const folders = await projectsResp.json();
      const match = Array.isArray(folders)
        ? (folders.find(
            (f: { name: string; id: string }) => f.name === "Starter Project",
          ) ?? folders[0])
        : null;
      folderId = (match as { id: string } | null)?.id ?? "";
    } catch {
      // proceed
    }

    await setupRoutesWithConnections(page, folderId);
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="subtab-deployments"]');

    // Open edit dialog
    await page
      .getByTestId("deployment-row-dep-1")
      .waitFor({ state: "visible" });
    await page.getByTestId("actions-deployment-dep-1").click();
    await page.getByRole("menuitem", { name: "Update" }).click();
    await page.waitForSelector('[data-testid="stepper-modal-title"]');

    // Step 1 (Type) → Next
    await page.waitForSelector('h2:has-text("Deployment Type")');
    await page.getByTestId("deployment-stepper-next").click();

    // Step 2 (Attach Flows)
    await page.waitForSelector("text=Attach Flows");
    await page.waitForSelector('[data-testid="flow-item-f1"]');
    await page.getByTestId("flow-item-f1").click();
    await page.waitForSelector('[data-testid="version-item-fv1"]');
    await page.getByTestId("version-item-fv1").click();

    // Wait for connection panel
    await page.waitForSelector('[data-testid="connection-item-existing-app"]');

    // Deselect the existing connection (uncheck it)
    await page.getByTestId("connection-item-existing-app").click();

    // Select only the new connection
    await page.getByTestId("connection-item-new-app").click();
    await page.getByTestId("connection-attach").click();

    // Step 3 (Review) → click Next
    await page.getByTestId("deployment-stepper-next").click();

    const patchRequestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments/dep-1") &&
        req.method() === "PATCH",
    );

    // Click Update
    await page.getByTestId("deployment-stepper-next").click();
    const patchRequest = await patchRequestPromise;
    const body = patchRequest.postDataJSON();

    const upsertFlows = body?.provider_data?.upsert_flows ?? [];
    const flowEntry = upsertFlows.find(
      (f: { flow_version_id: string }) => f.flow_version_id === "fv1",
    );
    expect(flowEntry).toBeDefined();
    expect(flowEntry.add_app_ids).toContain("new-app");
    expect(flowEntry.remove_app_ids).toContain("existing-app");
  },
);
