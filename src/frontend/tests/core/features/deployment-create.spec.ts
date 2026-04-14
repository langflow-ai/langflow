import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  CONFIGS_MOCK,
  DEPLOY_RESPONSE,
  FLOW_VERSIONS_MOCK,
  FLOWS_MOCK,
  LLMS_MOCK,
  PROVIDERS_MOCK,
  SNAPSHOTS_DUPLICATE_MOCK,
  SNAPSHOTS_EMPTY_MOCK,
} from "../../utils/deployment-mocks";

// ---------------------------------------------------------------------------
// Helper: set up all required API route mocks
// ---------------------------------------------------------------------------
async function setupDeploymentMocks(
  page: Page,
  folderId: string,
  snapshotsMock: object = SNAPSHOTS_EMPTY_MOCK,
) {
  // Broad catch-all registered FIRST so specific routes (registered after) take priority via LIFO
  await page.route("**/api/v1/deployments*", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ deployments: [] }),
    });
  });

  // Snapshots (used for duplicate tool name check on review step)
  await page.route("**/api/v1/deployments/snapshots**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(snapshotsMock),
    });
  });

  // Provider accounts
  await page.route("**/api/v1/deployments/providers**", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PROVIDERS_MOCK),
      });
    } else {
      route.continue();
    }
  });

  // LLMs
  await page.route("**/api/v1/deployments/llms**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LLMS_MOCK),
    });
  });

  // Deployment configs (connections)
  await page.route("**/api/v1/deployments/configs**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(CONFIGS_MOCK),
    });
  });

  // Flows list — inject the captured folderId so the component's folder filter passes
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

  // Global variables (used in attach-flows step)
  await page.route("**/api/v1/variables**", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

// ---------------------------------------------------------------------------
// Helper: navigate to the deployments page and open the stepper
// ---------------------------------------------------------------------------
async function openDeploymentStepper(
  page: Page,
  snapshotsMock: object = SNAPSHOTS_EMPTY_MOCK,
) {
  // Listen for the folders/projects API response BEFORE bootstrap to capture
  // the real myCollectionId. The step-attach-flows component filters flows by
  // folder_id === myCollectionId, so mock flows must carry the same id.
  const projectsResponsePromise = page.waitForResponse(
    (resp) => resp.url().includes("/api/v1/projects") && resp.status() === 200,
    { timeout: 30000 },
  );

  await awaitBootstrapTest(page, { skipModal: true });

  let myCollectionId = "";
  try {
    const projectsResp = await projectsResponsePromise;
    const folders = await projectsResp.json();
    const match = Array.isArray(folders)
      ? (folders.find(
          (f: { name: string; id: string }) => f.name === "Starter Project",
        ) ?? folders[0])
      : null;
    myCollectionId = (match as { id: string } | null)?.id ?? "";
  } catch {
    // proceed with empty id — test will likely fail at flow-item assertion
  }

  await setupDeploymentMocks(page, myCollectionId, snapshotsMock);
  await page.getByTestId("deployments-btn").click();
  await page.waitForSelector('[data-testid="subtab-deployments"]');
  await page.getByTestId("create-deployment-empty-btn").click();
  // Wait for the stepper dialog to appear
  await page.waitForSelector('[data-testid="deployment-stepper-next"]');
}

// ---------------------------------------------------------------------------
// Helper: select the provider in step 1
// ---------------------------------------------------------------------------
async function selectProvider(page: Page) {
  await page.getByTestId("provider-item-prov-1").click();
}

// ---------------------------------------------------------------------------
// Helper: navigate steps 1 → 2 (provider → type)
// ---------------------------------------------------------------------------
async function goToStepType(page: Page) {
  await selectProvider(page);
  await page.getByTestId("deployment-stepper-next").click();
  // Wait for the Type step heading
  await page.waitForSelector("text=Deployment Type");
}

// ---------------------------------------------------------------------------
// Helper: navigate steps 1 → 2 → 3 (provider → type → attach flows)
// ---------------------------------------------------------------------------
async function goToStepAttachFlows(page: Page) {
  await goToStepType(page);
  // Fill required fields: name and type
  await page.getByPlaceholder("e.g., Sales Bot").fill("My Deployment");
  await page.getByTestId("deployment-type-agent").click();
  // Select the LLM model
  await page.getByRole("combobox").click();
  await page.getByRole("option", { name: "ibm/granite-13b-chat" }).click();
  // Advance to attach flows
  await page.getByTestId("deployment-stepper-next").click();
  await page.waitForSelector("text=Attach Flows");
}

// ---------------------------------------------------------------------------
// Helper: navigate all steps through attach flows and select a flow+version
// ---------------------------------------------------------------------------
async function goToStepReview(page: Page) {
  await goToStepAttachFlows(page);
  // Click flow item
  await page.waitForSelector('[data-testid="flow-item-f1"]');
  await page.getByTestId("flow-item-f1").click();
  // Click version item
  await page.waitForSelector('[data-testid="version-item-fv1"]');
  await page.getByTestId("version-item-fv1").click();
  // After clicking version, a connection panel may appear - skip it if present
  const skipBtn = page.getByRole("button", { name: /skip/i });
  const skipVisible = await skipBtn.isVisible().catch(() => false);
  if (skipVisible) {
    await skipBtn.click();
  }
  // Advance to review
  await page.getByTestId("deployment-stepper-next").click();
  await page.waitForSelector("text=Review & Confirm");
}

// ---------------------------------------------------------------------------
// Test 1: Opens stepper on New Deployment click
// ---------------------------------------------------------------------------
test(
  "deployment-create: opens stepper on New Deployment click",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await awaitBootstrapTest(page, { skipModal: true });
    await setupDeploymentMocks(page, "");
    await page.getByTestId("deployments-btn").click();
    await page.waitForSelector('[data-testid="subtab-deployments"]');
    await page.getByTestId("create-deployment-empty-btn").click();

    await expect(page.getByTestId("stepper-modal-title")).toBeVisible();
    await expect(page.getByTestId("deployment-stepper-next")).toBeVisible();
  },
);

// ---------------------------------------------------------------------------
// Test 2: Step 1 (Provider) — Next disabled without selection, enabled after
// ---------------------------------------------------------------------------
test(
  "deployment-create: step 1 provider - Next disabled without selection, enabled after selecting",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);

    // Next should be disabled before selection
    await expect(page.getByTestId("deployment-stepper-next")).toBeDisabled();

    // Select the existing provider
    await selectProvider(page);

    // Next should now be enabled
    await expect(page.getByTestId("deployment-stepper-next")).toBeEnabled();
  },
);

// ---------------------------------------------------------------------------
// Test 3: Step 2 (Type) — fill name, select type, Next becomes enabled
// ---------------------------------------------------------------------------
test(
  "deployment-create: step 2 type - fill name and select type to enable Next",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);
    await selectProvider(page);
    await page.getByTestId("deployment-stepper-next").click();

    // Type step should be visible
    await expect(
      page.getByRole("heading", { name: /Deployment Type/i }),
    ).toBeVisible();

    // Next should be disabled before filling required fields
    await expect(page.getByTestId("deployment-stepper-next")).toBeDisabled();

    // Fill in the deployment name
    await page.getByPlaceholder("e.g., Sales Bot").fill("My Deployment");

    // Select the agent type
    await page.getByTestId("deployment-type-agent").click();

    // Select the LLM model
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "ibm/granite-13b-chat" }).click();

    // Next should now be enabled
    await expect(page.getByTestId("deployment-stepper-next")).toBeEnabled();
  },
);

// ---------------------------------------------------------------------------
// Test 4: Step 3 (Attach Flows) — select a flow and version, Next enables
// ---------------------------------------------------------------------------
test(
  "deployment-create: step 3 attach flows - select flow and version enables Next",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);
    await goToStepType(page);

    // Fill required type step fields
    await page.getByPlaceholder("e.g., Sales Bot").fill("My Deployment");
    await page.getByTestId("deployment-type-agent").click();
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "ibm/granite-13b-chat" }).click();
    await page.getByTestId("deployment-stepper-next").click();

    // Attach flows step should be visible
    await page.waitForSelector('[data-testid="flow-item-f1"]', {
      timeout: 20000,
    });

    // Click the flow item
    await page.waitForSelector('[data-testid="flow-item-f1"]');
    await page.getByTestId("flow-item-f1").click();

    // Version panel should appear, click the version
    await page.waitForSelector('[data-testid="version-item-fv1"]');
    await page.getByTestId("version-item-fv1").click();

    // Skip connection if prompted
    const skipBtn = page.getByRole("button", { name: /skip/i });
    const skipVisible = await skipBtn.isVisible().catch(() => false);
    if (skipVisible) {
      await skipBtn.click();
    }

    // Next should be enabled after version selection
    await expect(page.getByTestId("deployment-stepper-next")).toBeEnabled();
  },
);

// ---------------------------------------------------------------------------
// Test 5: Step 4 (Review) — shows review content and Deploy button
// ---------------------------------------------------------------------------
test(
  "deployment-create: step 4 review - shows review content and Deploy button text",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);
    await goToStepReview(page);

    // Review heading and content should be visible
    await expect(
      page.getByRole("heading", { name: /Review & Confirm/i }),
    ).toBeVisible();

    // The deployment name should appear in the review
    await expect(page.getByText("My Deployment")).toBeVisible();

    // The Next/Deploy button text should be "Deploy"
    await expect(page.getByTestId("deployment-stepper-next")).toContainText(
      "Deploy",
    );
  },
);

// ---------------------------------------------------------------------------
// Test 6: Deploy triggers POST, shows deploy status
// ---------------------------------------------------------------------------
test(
  "deployment-create: clicking Deploy triggers POST and shows deploy status",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);

    // Set up POST deployments mock (after bootstrap, before deploy click)
    await page.route("**/api/v1/deployments", (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(DEPLOY_RESPONSE),
        });
      } else {
        route.continue();
      }
    });
    await goToStepReview(page);

    // Watch for the POST request
    const postRequestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/v1/deployments") &&
        req.method() === "POST" &&
        !req.url().includes("/providers") &&
        !req.url().includes("/llms") &&
        !req.url().includes("/configs"),
    );

    // Click Deploy
    await page.getByTestId("deployment-stepper-next").click();

    // Assert the POST request was made
    await postRequestPromise;

    // Assert deploy status content is shown (either deploying or deployed state)
    await expect(
      page.getByRole("heading", {
        name: /Deploying\.\.\.|Deployment successful/i,
      }),
    ).toBeVisible({ timeout: 10000 });
  },
);

// ---------------------------------------------------------------------------
// Test 7: Review step — user can change tool name
// ---------------------------------------------------------------------------
test(
  "deployment-create: user can change tool name on review step",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page);
    await goToStepReview(page);

    // The edit tool name button should be visible on the review step
    await expect(page.getByTestId("edit-tool-name")).toBeVisible();

    // Click the edit (pencil) button to enter editing mode
    await page.getByTestId("edit-tool-name").click();

    // The tool name input should appear
    const toolNameInput = page.getByTestId("tool-name-input");
    await expect(toolNameInput).toBeVisible();

    // Clear and type a new tool name
    await toolNameInput.fill("Custom Tool Name");

    // Confirm the change by pressing Enter
    await toolNameInput.press("Enter");

    // The input should disappear and the new name should be visible
    await expect(toolNameInput).not.toBeVisible();
    await expect(page.getByText("Custom Tool Name")).toBeVisible();
  },
);

// ---------------------------------------------------------------------------
// Test 8: Review step — shows duplicate tool name error when provider has existing tool
// ---------------------------------------------------------------------------
test(
  "deployment-create: review step shows error when tool name already exists in provider",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page, SNAPSHOTS_DUPLICATE_MOCK);
    await goToStepReview(page);

    // The duplicate tool name error should appear
    await expect(
      page.getByText("Edit tool name (already exists in provider)"),
    ).toBeVisible({ timeout: 10000 });

    // Deploy button should be disabled while there are tool name errors
    await expect(page.getByTestId("deployment-stepper-next")).toBeDisabled();
  },
);

// ---------------------------------------------------------------------------
// Test 9: Review step — no error when tool name does not exist in provider
// ---------------------------------------------------------------------------
test(
  "deployment-create: review step shows no error when tool name is unique",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page, SNAPSHOTS_EMPTY_MOCK);
    await goToStepReview(page);

    // No duplicate error should be present
    await expect(
      page.getByText("Edit tool name (already exists in provider)"),
    ).not.toBeVisible();

    // Deploy button should be enabled
    await expect(page.getByTestId("deployment-stepper-next")).toBeEnabled();
  },
);

// ---------------------------------------------------------------------------
// Test 10: Review step — fixing duplicate tool name clears error
// ---------------------------------------------------------------------------
test(
  "deployment-create: editing tool name to unique value clears duplicate error",
  { tag: ["@deployment", "@workspace"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await openDeploymentStepper(page, SNAPSHOTS_DUPLICATE_MOCK);
    await goToStepReview(page);

    // Error should be visible initially
    await expect(
      page.getByText("Edit tool name (already exists in provider)"),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("deployment-stepper-next")).toBeDisabled();

    // Override the snapshots mock to return empty (unique name) for the next check
    await page.route("**/api/v1/deployments/snapshots**", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SNAPSHOTS_EMPTY_MOCK),
      });
    });

    // Edit the tool name to something unique
    await page.getByTestId("edit-tool-name").click();
    const toolNameInput = page.getByTestId("tool-name-input");
    await toolNameInput.fill("Unique Tool Name");
    await toolNameInput.press("Enter");

    // Error should clear and deploy button should re-enable
    await expect(
      page.getByText("Edit tool name (already exists in provider)"),
    ).not.toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("deployment-stepper-next")).toBeEnabled();
  },
);
