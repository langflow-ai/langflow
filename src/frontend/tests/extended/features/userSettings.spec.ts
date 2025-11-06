import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.beforeAll(async () => {
  await new Promise((resolve) => setTimeout(resolve, 10000));
});

test.afterEach(async () => {
  await new Promise((resolve) => setTimeout(resolve, 10000));
});

test(
  "should see general profile gradient",
  { tag: ["@release"] },

  async ({ page }) => {
    await awaitBootstrapTest(page, {
      skipModal: true,
    });
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });
    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Settings").click();

    // Wait for settings page to fully load
    await page
      .waitForLoadState("networkidle", { timeout: 10000 })
      .catch(() => {});
    await page.waitForTimeout(1000);

    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("Profile Picture").first()).toBeVisible();
  },
);

test(
  "should interact with global variables",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const randomName2 = Math.random().toString(36).substring(2);
    const randomName3 = Math.random().toString(36).substring(2);

    await awaitBootstrapTest(page, {
      skipModal: true,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Settings").click();
    await page.getByText("Global Variables").click();
    await expect(
      page.getByText("Global Variables", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });
    await page.getByText("Add New").click();
    await page
      .getByPlaceholder("Enter a name for the variable...")
      .fill(randomName);
    await expect(page.getByText("Generic", { exact: true }).last()).toBeVisible(
      { timeout: 10000 },
    );
    await page.getByText("Generic", { exact: true }).last().click();

    await page
      .getByPlaceholder("Enter a value for the variable...")
      .fill("testtesttesttesttesttesttesttest");
    await page.getByTestId("popover-anchor-apply-to-fields").click();

    await page.getByPlaceholder("Fields").waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page.getByPlaceholder("Fields").fill("AgentQL API Key");

    await page.waitForSelector("text=AgentQL API Key", { timeout: 30000 });

    await page.getByText("AgentQL API Key").last().click();

    await page.getByPlaceholder("Fields").fill("openAI");

    await page.waitForSelector("text=openai", { timeout: 30000 });

    await page.getByText("openai").last().click();

    // Wait for the field to be ready for input
    await page.getByPlaceholder("Fields").waitFor({
      state: "visible",
      timeout: 30000,
    });

    // Additional wait for field to be fully interactive
    await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {
      // Continue if network idle timeout
    });

    await page.getByPlaceholder("Fields").fill("ollama");

    await page.keyboard.press("Escape");
    await page.getByText("Save Variable", { exact: true }).click();

    await expect(page.getByText(randomName).last()).toBeVisible({
      timeout: 10000,
    });

    await page.getByText(randomName).last().click();
    await page.getByText(randomName).last().click();

    await page.getByPlaceholder("Enter a name for the variable...").waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByPlaceholder("Enter a name for the variable...")
      .fill(randomName2);

    await page.getByText("Update Variable", { exact: true }).last().click();

    await expect(page.getByText(randomName2).last()).toBeVisible({
      timeout: 10000,
    });

    await page.getByText(randomName2).last().click();

    await page.getByPlaceholder("Enter a name for the variable...").waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByPlaceholder("Enter a name for the variable...")
      .fill(randomName3);

    await page.getByText("Update Variable", { exact: true }).last().click();

    await expect(page.getByText(randomName3).last()).toBeVisible({
      timeout: 10000,
    });

    await page.locator(".ag-checkbox-input").first().click();
    await page.getByTestId("icon-Trash2").click();
    await expect(page.getByText("No data available")).toBeVisible({
      timeout: 10000,
    });
  },
);

test("should see shortcuts", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page, {
    skipModal: true,
  });
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });
  await page.getByTestId("user-profile-settings").click();

  await page.getByText("Settings").click();

  // Wait for settings page to fully load
  await page
    .waitForLoadState("networkidle", { timeout: 10000 })
    .catch(() => {});
  await page.waitForTimeout(1000);

  await expect(page.getByText("General").nth(2)).toBeVisible({
    timeout: 10000,
  });
  await page.getByText("Shortcuts").nth(0).click();

  // Wait for shortcuts section to load
  await page.waitForTimeout(1000);

  await expect(page.getByText("Shortcuts", { exact: true }).nth(1)).toBeVisible(
    { timeout: 10000 },
  );
  await expect(page.getByText("Controls", { exact: true })).toBeVisible({
    timeout: 10000,
  });

  await expect(
    page.getByText("Search Components on Sidebar", { exact: true }),
  ).toBeVisible({ timeout: 10000 });

  await expect(page.getByText("Minimize", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Code", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Copy", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Duplicate", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Component Share", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Docs", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Changes Save", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Delete", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Open Playground", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Undo", { exact: true })).toBeVisible({
    timeout: 10000,
  });

  await page.mouse.wheel(0, 10000);

  await expect(page.getByText("Redo", { exact: true }).last()).toBeVisible({
    timeout: 10000,
  });

  await expect(
    page.getByText("Redo (alternative)", { exact: true }).last(),
  ).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Group").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Cut").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Paste").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("API").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Download").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Update").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Freeze").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Flow Share").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Play").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Output Inspection").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Tool Mode").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Toggle Sidebar").last()).toBeVisible({
    timeout: 10000,
  });
});

test(
  "should interact with API Keys",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, {
      skipModal: true,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Settings").click();

    // Wait for settings page to fully load
    await page
      .waitForLoadState("networkidle", { timeout: 10000 })
      .catch(() => {});
    await page.waitForTimeout(1000);

    await page.getByText("Langflow API").first().click();

    // Wait for API section to load
    await page.waitForTimeout(1000);

    await expect(
      page.getByText("Langflow API Keys", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });
    await page.getByText("Add New").click();
    await expect(page.getByPlaceholder("My API Key")).toBeVisible({
      timeout: 10000,
    });

    const randomName = Math.random().toString(36).substring(2);

    await page.getByPlaceholder("My API Key").fill(randomName);
    await page.getByText("Generate API Key", { exact: true }).click();

    // Wait for api key creation to complete
    await page.waitForSelector("text=Please save", { timeout: 30000 });
    await page.waitForSelector('[data-testid="btn-copy-api-key"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("btn-copy-api-key").click();

    await page.waitForSelector("text=Api Key Copied!", { timeout: 30000 });

    await page.getByTestId("secret_key_modal_submit_button").click();

    await page.mouse.wheel(0, 10000);

    await expect(page.getByText(randomName)).toBeVisible({ timeout: 10000 });
  },
);

test(
  "should navigate back to flow from global variables",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    // Now navigate to user settings
    await page.getByTestId("user-profile-settings").click();
    await page.getByTestId("menu_settings_button").click();

    // Verify we're on the settings page
    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 4000,
    });

    // Navigate to Global Variables
    await page.getByText("Global Variables").click();
    await expect(
      page.getByText("Global Variables", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });

    // Click the back button - this should take us back to the flow, not to the main settings page
    await page.getByTestId("back_page_button").click();

    // Verify we're back on the flow page, not the settings main page
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    // Additional verification that we're on the flow page
    expect(page.url()).toMatch(/\/flow\//);

    // Verify we can see flow-specific elements
    await expect(page.getByTestId("sidebar-search-input")).toBeVisible();
  },
);
