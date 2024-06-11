import { test } from "@playwright/test";

test("should see general profile gradient", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByTestId("user-profile-settings").click();
  await page.waitForTimeout(1000);

  await page.getByText("Settings").click();
  await page.waitForTimeout(3000);

  await page.getByText("General").nth(2).isVisible();
  await page.getByText("Profile Gradient").isVisible();
});

test("should interact with global variables", async ({ page }) => {
  const randomName = Math.random().toString(36).substring(2);

  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByTestId("user-profile-settings").click();
  await page.getByText("Settings").click();
  await page.getByText("Global Variables").click();
  await page.getByText("Global Variables").nth(2);
  await page.getByText("Global Variables", { exact: true }).nth(1).isVisible();
  await page.getByText("Add New").click();
  await page
    .getByPlaceholder("Insert a name for the variable...")
    .fill(randomName);
  await page.getByTestId("popover-anchor-type-global-variables").click();
  await page.getByPlaceholder("Search options...").fill("Generic");
  await page.waitForTimeout(2000);
  await page.getByText("Generic", { exact: true }).last().isVisible();
  await page.getByText("Generic", { exact: true }).last().click();

  await page.getByTestId("popover-anchor-type-global-variables").click();
  await page.waitForTimeout(2000);
  await page.getByPlaceholder("Search options...").fill("Generic");
  await page.getByText("Generic", { exact: true }).last().isVisible();
  await page.getByText("Generic", { exact: true }).last().click();

  await page
    .getByPlaceholder("Insert a value for the variable...")
    .fill("testtesttesttesttesttesttesttest");
  await page.getByTestId("popover-anchor-apply-to-fields").click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search options...").fill("System Message");

  await page.getByText("System Message").first().click();

  await page.getByPlaceholder("Search options...").fill("openAI");

  await page.getByText("OpenAI API Base").first().click();

  await page.getByPlaceholder("Search options...").fill("llama");

  await page.getByText("Ollama").first().click();

  await page.keyboard.press("Escape");
  await page.getByText("Save Variable", { exact: true }).click();

  await page.getByText(randomName).isVisible();

  await page
    .getByLabel("Press Space to toggle all rows selection (unchecked)")
    .nth(0)
    .click();
  await page.getByTestId("icon-Trash2").click();
  await page.getByText("No data available").isVisible();
});

test("should see shortcuts", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByTestId("user-profile-settings").click();
  await page.waitForTimeout(1000);

  await page.getByText("Settings").click();
  await page.waitForTimeout(3000);

  await page.getByText("General").nth(2).isVisible();
  await page.getByText("Shortcuts").nth(0).click();
  await page.getByText("Shortcuts", { exact: true }).nth(1).isVisible();
  await page
    .getByText("Advanced Settings Component", { exact: true })
    .isVisible();
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

test("should interact with API Keys", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);
  await page.getByTestId("user-profile-settings").click();
  await page.getByText("Settings").click();
  await page.getByText("Langflow API").click();
  await page.getByText("Langflow API", { exact: true }).nth(1).isVisible();
  await page.getByText("Add New").click();
  await page.getByPlaceholder("Insert a name for your API Key").isVisible();

  const randomName = Math.random().toString(36).substring(2);

  await page
    .getByPlaceholder("Insert a name for your API Key")
    .fill(randomName);
  await page.getByText("Create Secret Key", { exact: true }).click();
  await page.getByText("Please save").isVisible();
  await page.getByTestId("icon-Copy").click();
  await page.waitForTimeout(1000);
  await page.getByText("Api Key Copied!").isVisible();
  await page.getByText(randomName).isVisible();
});
