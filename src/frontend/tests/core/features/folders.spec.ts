import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "CRUD folders",
  { tag: ["@release", "@api"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();
    await page.getByPlaceholder("Search flows").first().isVisible();
    await page.getByText("Flows").first().isVisible();
    if (await page.getByText("Components").first().isVisible()) {
      await page.getByText("Components").first().isVisible();
    } else {
      await page.getByText("MCP Server").first().isVisible();
    }
    await page.getByText("All").first().isVisible();
    await page.getByText("Select All").first().isVisible();

    await page.getByTestId("add-project-button").click();
    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .isVisible();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    const element = await page.getByTestId("input-project");
    await element.fill("new project test name");

    await page.getByText("Starter Project").last().click({
      force: true,
    });

    await page.getByText("new project test name").last().waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByText("new project test name")
      .last()
      .hover()
      .then(async () => {
        await page.getByTestId("more-options-button").last().click();
      });

    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();
    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 3000,
    });
  },
);

test("add a flow into a folder by drag and drop", async ({ page }) => {
  await page.goto("/");

  await page.waitForSelector("text=New Flow", {
    timeout: 50000,
  });

  const jsonContent = readFileSync("tests/assets/collection.json", "utf-8");

  // Wait for the target element to be available before evaluation

  await page.waitForSelector('[data-testid="sidebar-nav-My Projects"]', {
    timeout: 100000,
  });
  // Create the DataTransfer and File
  const dataTransfer = await page.evaluateHandle((data) => {
    const dt = new DataTransfer();
    // Convert the buffer to a hex array
    const file = new File([data], "flowtest.json", {
      type: "application/json",
    });
    dt.items.add(file);
    return dt;
  }, jsonContent);

  // Now dispatch
  await page.getByTestId("sidebar-nav-My Projects").dispatchEvent("drop", {
    dataTransfer,
  });
  // wait for the file to be uploaded failed with waitforselector

  await page.waitForTimeout(1000);

  const genericNode = page.getByTestId("div-generic-node");
  const elementCount = await genericNode?.count();
  if (elementCount > 0) {
    expect(true).toBeTruthy();
  }

  await page.getByTestId("sidebar-nav-My Projects").click();

  await page.waitForSelector("text=Getting Started:", {
    timeout: 100000,
  });

  expect(
    await page.locator("text=Getting Started:").last().isVisible(),
  ).toBeTruthy();
  expect(
    await page.locator("text=Inquisitive Pike").last().isVisible(),
  ).toBeTruthy();
  expect(
    await page.locator("text=Dreamy Bassi").last().isVisible(),
  ).toBeTruthy();
  expect(
    await page.locator("text=Furious Faraday").last().isVisible(),
  ).toBeTruthy();
});

test("change flow folder", async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByPlaceholder("Search flows").isVisible();
  await page.getByText("Flows").first().isVisible();
  if (await page.getByText("Components").first().isVisible()) {
    await page.getByText("Components").first().isVisible();
  } else {
    await page.getByText("MCP Server").first().isVisible();
  }

  await page.getByTestId("add-project-button").click();
  await page
    .locator("[data-testid='project-sidebar']")
    .getByText("New Project")
    .last()
    .isVisible();
  await page
    .locator("[data-testid='project-sidebar']")
    .getByText("New Project")
    .last()
    .dblclick();
  await page.getByTestId("input-project").fill("new project test name");
  await page.keyboard.press("Enter");
  await page.getByText("new project test name").last().isVisible();

  await page.getByText("Starter Project").last().click();
  await page.getByText("Basic Prompting").first().hover();
  await page.mouse.down();
  await page.getByText("test").first().hover();
  await page.mouse.up();
  await page.getByText("Basic Prompting").first().isVisible();
});
