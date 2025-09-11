import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.beforeAll(async () => {
  await new Promise((resolve) => setTimeout(resolve, 7000));
});

test.afterEach(async () => {
  await new Promise((resolve) => setTimeout(resolve, 7000));
});

test(
  "should see general profile gradient",
  { tag: ["@release"] },

  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });
    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Settings").click();

    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 4000,
    });
    await page.getByText("Profile Gradient").isVisible();
  },
);

test(
  "should interact with global variables",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const randomName2 = Math.random().toString(36).substring(2);
    const randomName3 = Math.random().toString(36).substring(2);

    await page.goto("/");
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Settings").click();
    await page.getByText("Global Variables").click();
    await page.getByText("Global Variables").nth(2);
    await page
      .getByText("Global Variables", { exact: true })
      .nth(1)
      .isVisible();
    await page.getByText("Add New").click();
    await page
      .getByPlaceholder("Enter a name for the variable...")
      .fill(randomName);
    await page.getByText("Generic", { exact: true }).last().isVisible();
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

    await page.waitForTimeout(1000);

    await page.getByPlaceholder("Fields").waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page.waitForTimeout(1000);

    await page.getByPlaceholder("Fields").fill("ollama");

    await page.keyboard.press("Escape");
    await page.getByText("Save Variable", { exact: true }).click();

    await page.getByText(randomName).last().isVisible();

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

    await page.getByText(randomName2).last().isVisible();

    await page.getByText(randomName2).last().click();

    await page.getByPlaceholder("Enter a name for the variable...").waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByPlaceholder("Enter a name for the variable...")
      .fill(randomName3);

    await page.getByText("Update Variable", { exact: true }).last().click();

    await page.getByText(randomName3).last().isVisible();

    await page.locator(".ag-checkbox-input").first().click();
    await page.getByTestId("icon-Trash2").click();
    await page.getByText("No data available").isVisible();
  },
);

test("should see shortcuts", { tag: ["@release"] }, async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });
  await page.getByTestId("user-profile-settings").click();

  await page.getByText("Settings").click();

  await page.getByText("General").nth(2).isVisible();
  await page.getByText("Shortcuts").nth(0).click();
  await page.getByText("Shortcuts", { exact: true }).nth(1).isVisible();
  await page.getByText("Controls Component", { exact: true }).isVisible();
  await page.getByText("Minimize Component", { exact: true }).isVisible();
  await page.getByText("Code Component", { exact: true }).isVisible();
  await page.getByText("Copy Component", { exact: true }).isVisible();
  await page.getByText("Duplicate Component", { exact: true }).isVisible();
  await page.getByText("Share Component", { exact: true }).isVisible();
  await page.getByText("Docs Component", { exact: true }).isVisible();
  await page.getByText("Save Component", { exact: true }).isVisible();
  await page.getByText("Delete Component", { exact: true }).isVisible();
  await page.getByText("Open Playground", { exact: true }).isVisible();
  await page.getByText("Undo", { exact: true }).isVisible();

  await page.mouse.wheel(0, 10000);

  await page.getByText("Redo", { exact: true }).last().isVisible();

  await page.getByText("Reset Columns").last().isVisible();
});

test(
  "should interact with API Keys",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Settings").click();
    await page.getByText("Langflow API").first().click();
    await page.getByText("Langflow API", { exact: true }).nth(1).isVisible();
    await page.getByText("Add New").click();
    await page.getByPlaceholder("My API Key").isVisible();

    const randomName = Math.random().toString(36).substring(2);

    await page.getByPlaceholder("My API Key").fill(randomName);
    await page.getByText("Generate API Key", { exact: true }).click();

    // Wait for api key creation to complete and render the next form element
    await page.waitForTimeout(1000);

    await page.waitForSelector("text=Please save", { timeout: 30000 });
    await page.waitForSelector('[data-testid="btn-copy-api-key"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("btn-copy-api-key").click();

    await page.waitForSelector("text=Api Key Copied!", { timeout: 30000 });

    await page.getByText(randomName).isVisible();
  },
);

test(
  "should navigate back to flow from global variables",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("canvas_controls_dropdown").click();

    // Now navigate to user settings
    await page.getByTestId("user-profile-settings").click();
    await page.getByTestId("menu_settings_button").click();

    // Verify we're on the settings page
    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 4000,
    });

    // Navigate to Global Variables
    await page.getByText("Global Variables").click();
    await page.getByText("Global Variables").nth(2);
    await page
      .getByText("Global Variables", { exact: true })
      .nth(1)
      .isVisible();

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
