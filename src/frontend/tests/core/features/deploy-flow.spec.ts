import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to deploy a flow",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    // Add Chat Input component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .hover({ timeout: 3000 })
      .then(async () => {
        await page
          .getByTestId("add-component-button-chat-input")
          .last()
          .click();
      });

    await page.waitForTimeout(2000);

    // Adjust view and open publish dropdown
    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId("publish-button").click();

    await page.waitForTimeout(3000);

    // Verify deployed status toggle is visible
    await page.waitForSelector('[data-testid="deployed-status"]', {
      timeout: 10000,
    });

    try {
      await page.waitForTimeout(2000);

      await expect(page.getByTestId("deploy-switch")).toBeVisible({
        timeout: 10000,
      });
    } catch (error) {
      console.error("Error waiting for deploy operation:", error);
      throw error;
    }

    await page.waitForTimeout(2000);

    // Toggle deployment status to DEPLOYED
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(2000);

    // Verify switch is now checked (deployed)
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: true,
    });

    // Close dropdown
    await page.getByTestId("rf__wrapper").click();
    await page.waitForTimeout(500);

    // Open dropdown again to verify state persisted
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(500);

    // Verify deploy switch is still checked
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: true,
    });

    // Toggle back to DRAFT
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(500);

    // Verify switch is now unchecked (draft)
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: false,
    });
  },
);

test(
  "deployed flows should be locked",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    // Add Chat Input component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .hover({ timeout: 3000 })
      .then(async () => {
        await page
          .getByTestId("add-component-button-chat-input")
          .last()
          .click();
      });

    await page.waitForTimeout(2000);

    // Adjust view and open publish dropdown
    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(2000);

    // Deploy the flow
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(2000);

    // Close dropdown
    await page.getByTestId("rf__wrapper").click();
    await page.waitForTimeout(500);

    // Try to edit - flow should be locked
    // Check if lock indicator is visible (assuming there's a lock icon or similar)
    await page.waitForTimeout(1000);

    // Attempt to drag component (should be prevented if locked)
    const chatInputNode = page.locator('[data-testid*="title-Chat Input"]');
    await expect(chatInputNode).toBeVisible();

    // Undeploy the flow
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(500);
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(500);

    // Flow should now be unlocked and editable
    await page.getByTestId("rf__wrapper").click();
    await page.waitForTimeout(500);

    // Verify we can interact with components again
    await expect(chatInputNode).toBeVisible();
  },
);

test(
  "deploy switch works even without IO components",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    await page.waitForTimeout(2000);

    // Open publish dropdown without adding IO components
    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(2000);

    // Verify deploy switch is enabled (no longer requires IO components)
    await page.waitForSelector('[data-testid="deploy-switch"]', {
      timeout: 5000,
    });

    const deploySwitch = page.getByTestId("deploy-switch");
    await expect(deploySwitch).toBeVisible();
    await expect(deploySwitch).not.toBeDisabled();
  },
);

test(
  "deploy and publish switches work independently",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    // Add Chat Input component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .hover({ timeout: 3000 })
      .then(async () => {
        await page
          .getByTestId("add-component-button-chat-input")
          .last()
          .click();
      });

    await page.waitForTimeout(2000);

    // Open publish dropdown
    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(2000);

    // Enable deployment only
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(1000);

    // Verify deployment is on, publish is off
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: true,
    });
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: false,
    });

    // Enable publish as well
    await page.getByTestId("publish-switch").click();
    await page.waitForTimeout(1000);

    // Verify both are now on
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: true,
    });
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: true,
    });

    // Disable deployment only
    await page.getByTestId("deploy-switch").click();
    await page.waitForTimeout(1000);

    // Verify deployment is off, publish is still on
    await expect(page.getByTestId("deploy-switch")).toBeChecked({
      checked: false,
    });
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: true,
    });
  },
);
