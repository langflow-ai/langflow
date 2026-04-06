import { type Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  COMPLETED_EXECUTION_RESPONSE,
  DEPLOYMENTS_MOCK,
  POST_EXECUTION_RESPONSE,
  PROVIDERS_MOCK,
  RUNNING_EXECUTION_RESPONSE,
} from "../../utils/deployment-mocks";

async function setupBaseRoutes(page: Page) {
  // Register broad catch-all FIRST so specific routes (registered after) take priority via LIFO
  await page.route("**/api/v1/deployments*", (route) => {
    const url = route.request().url();
    // Execution routes are handled per-test; fall through for those
    if (url.includes("/dep-1/executions") || url.includes("/executions")) {
      route.fallback();
      return;
    }
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
}

async function navigateToDeploymentsPage(page: Page) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.getByTestId("deployments-btn").click();
  await page.waitForSelector('[data-testid="new-deployment-btn"]');
}

test(
  "Test button opens modal with chat interface",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    await setupBaseRoutes(page);
    await navigateToDeploymentsPage(page);

    await page.getByTestId("test-deployment-dep-1").click();

    await expect(page.getByTestId("test-deployment-modal-title")).toBeVisible();
    await expect(page.getByPlaceholder("Message")).toBeVisible();
  },
);

test(
  "Send message calls POST execution with correct body",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let capturedRequestBody: Record<string, unknown> | null = null;
    let executionCallCount = 0;

    await setupBaseRoutes(page);

    await page.route(
      "**/api/v1/deployments/dep-1/executions/exec-1",
      (route) => {
        executionCallCount++;
        const isCompleted = executionCallCount > 1;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            isCompleted
              ? COMPLETED_EXECUTION_RESPONSE
              : RUNNING_EXECUTION_RESPONSE,
          ),
        });
      },
    );

    await page.route(
      "**/api/v1/deployments/dep-1/executions",
      async (route) => {
        if (route.request().method() === "POST") {
          const body = route.request().postDataJSON() as Record<
            string,
            unknown
          >;
          capturedRequestBody = body;
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(POST_EXECUTION_RESPONSE),
          });
        } else {
          route.fallback();
        }
      },
    );

    await navigateToDeploymentsPage(page);

    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    await page.getByPlaceholder("Message").fill("Hello AI");
    await page.getByRole("button", { name: /send message/i }).click();

    await expect
      .poll(() => capturedRequestBody, { timeout: 10_000 })
      .toMatchObject({
        provider_data: { input: "Hello AI" },
      });
  },
);

test(
  "Response appears in chat after polling completes",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let executionCallCount = 0;

    await setupBaseRoutes(page);

    await page.route(
      "**/api/v1/deployments/dep-1/executions/exec-1",
      (route) => {
        executionCallCount++;
        const isCompleted = executionCallCount > 1;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            isCompleted
              ? COMPLETED_EXECUTION_RESPONSE
              : RUNNING_EXECUTION_RESPONSE,
          ),
        });
      },
    );

    await page.route(
      "**/api/v1/deployments/dep-1/executions",
      async (route) => {
        if (route.request().method() === "POST") {
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(POST_EXECUTION_RESPONSE),
          });
        } else {
          route.fallback();
        }
      },
    );

    await navigateToDeploymentsPage(page);

    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    await page.getByPlaceholder("Message").fill("Hello AI");
    await page.getByRole("button", { name: /send message/i }).click();

    await expect(page.getByText("Hello from AI")).toBeVisible({
      timeout: 30_000,
    });
    expect(executionCallCount).toBeGreaterThanOrEqual(2);
  },
);

test(
  "Input is disabled during polling and re-enabled after response",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let executionCallCount = 0;

    await setupBaseRoutes(page);

    await page.route(
      "**/api/v1/deployments/dep-1/executions/exec-1",
      (route) => {
        executionCallCount++;
        const isCompleted = executionCallCount > 1;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            isCompleted
              ? COMPLETED_EXECUTION_RESPONSE
              : RUNNING_EXECUTION_RESPONSE,
          ),
        });
      },
    );

    await page.route(
      "**/api/v1/deployments/dep-1/executions",
      async (route) => {
        if (route.request().method() === "POST") {
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(POST_EXECUTION_RESPONSE),
          });
        } else {
          route.fallback();
        }
      },
    );

    await navigateToDeploymentsPage(page);

    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    await page.getByPlaceholder("Message").fill("Hello AI");
    await page.getByRole("button", { name: /send message/i }).click();

    // Textarea should be disabled while waiting for response
    await expect(page.getByPlaceholder("Message")).toBeDisabled();

    // After response arrives, textarea should be re-enabled
    await expect(page.getByText("Hello from AI")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByPlaceholder("Message")).toBeEnabled();
  },
);

test(
  "Multi-turn: second message includes thread_id from first response",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let executionCallCount = 0;
    const capturedBodies: Array<Record<string, unknown>> = [];

    await setupBaseRoutes(page);

    await page.route(
      "**/api/v1/deployments/dep-1/executions/exec-1",
      (route) => {
        executionCallCount++;
        const isCompleted = executionCallCount % 2 === 0;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            isCompleted
              ? COMPLETED_EXECUTION_RESPONSE
              : RUNNING_EXECUTION_RESPONSE,
          ),
        });
      },
    );

    await page.route(
      "**/api/v1/deployments/dep-1/executions",
      async (route) => {
        if (route.request().method() === "POST") {
          const body = route.request().postDataJSON() as Record<
            string,
            unknown
          >;
          capturedBodies.push(body);
          // Reset poll counter for each new execution so each returns running then completed
          executionCallCount = 0;
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(POST_EXECUTION_RESPONSE),
          });
        } else {
          route.fallback();
        }
      },
    );

    await navigateToDeploymentsPage(page);

    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    // First message
    await page.getByPlaceholder("Message").fill("First message");
    await page.getByRole("button", { name: /send message/i }).click();

    // Wait for first response
    await expect(page.getByText("Hello from AI")).toBeVisible({
      timeout: 30_000,
    });

    // Second message
    await page.getByPlaceholder("Message").fill("Second message");
    await page.getByRole("button", { name: /send message/i }).click();

    // Wait for second response
    await expect(page.getByText("Hello from AI")).toHaveCount(2, {
      timeout: 30_000,
    });

    // Second POST should include thread_id from first response
    expect(capturedBodies).toHaveLength(2);
    expect(capturedBodies[1]).toMatchObject({
      provider_data: {
        input: "Second message",
        thread_id: "thread-1",
      },
    });
  },
);

test(
  "Close and reopen modal resets chat history",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(
      process.env.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );

    let executionCallCount = 0;

    await setupBaseRoutes(page);

    await page.route(
      "**/api/v1/deployments/dep-1/executions/exec-1",
      (route) => {
        executionCallCount++;
        const isCompleted = executionCallCount > 1;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            isCompleted
              ? COMPLETED_EXECUTION_RESPONSE
              : RUNNING_EXECUTION_RESPONSE,
          ),
        });
      },
    );

    await page.route(
      "**/api/v1/deployments/dep-1/executions",
      async (route) => {
        if (route.request().method() === "POST") {
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(POST_EXECUTION_RESPONSE),
          });
        } else {
          route.fallback();
        }
      },
    );

    await navigateToDeploymentsPage(page);

    // Open modal and send a message
    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    await page.getByPlaceholder("Message").fill("Hello AI");
    await page.getByRole("button", { name: /send message/i }).click();

    // Wait for response to appear
    await expect(page.getByText("Hello from AI")).toBeVisible({
      timeout: 30_000,
    });

    // Close the modal by pressing Escape
    await page.keyboard.press("Escape");

    // Verify the modal is closed
    await expect(page.getByPlaceholder("Message")).not.toBeVisible();

    // Reopen the modal
    executionCallCount = 0;
    await page.getByTestId("test-deployment-dep-1").click();
    await expect(page.getByPlaceholder("Message")).toBeVisible();

    // Chat should be empty — no previous messages visible
    await expect(page.getByText("Hello AI")).not.toBeVisible();
    await expect(page.getByText("Hello from AI")).not.toBeVisible();

    // Empty state ("Agent Chat") should be shown
    await expect(page.getByText("Agent Chat")).toBeVisible();
  },
);
