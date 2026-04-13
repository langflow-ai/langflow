import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { renameFlow } from "../../utils/rename-flow";

test(
  "CRUD folders",
  { tag: ["@release", "@api"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
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

    await page.getByTestId("sidebar-nav-new project test name").last().hover();

    await page
      .getByTestId("more-options-button_new-project-test-name")
      .waitFor({ state: "visible", timeout: 5000 });

    await page.getByTestId("more-options-button_new-project-test-name").click();

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

  await page.waitForSelector('[data-testid="sidebar-nav-Starter Project"]', {
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
  await page.getByTestId("sidebar-nav-Starter Project").dispatchEvent("drop", {
    dataTransfer,
  });
  // wait for the file to be uploaded failed with waitforselector

  await page.waitForTimeout(1000);

  const genericNode = page.getByTestId("div-generic-node");
  const elementCount = await genericNode?.count();
  if (elementCount > 0) {
    expect(true).toBeTruthy();
  }

  await page.getByTestId("sidebar-nav-Starter Project").click();

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
  const uniqueFlowName = `move-${Math.random().toString(36).substring(2, 10)}`;
  const destinationProjectName = `dest-${Math.random().toString(36).substring(2, 10)}`;

  await awaitBootstrapTest(page);

  // Create a flow in the Starter Project and rename it to something
  // unique so our assertions can't collide with any template that
  // Starter ships with by default.
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });
  await page.waitForTimeout(1000);

  await renameFlow(page, { flowName: uniqueFlowName });

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-ChevronLeft").first().click();
  await expect(page.getByPlaceholder("Search flows")).toBeVisible();

  await page.getByTestId("add-project-button").click();
  await page
    .locator("[data-testid='project-sidebar']")
    .getByText("New Project")
    .last()
    .waitFor({ state: "visible", timeout: 10000 });
  await page
    .locator("[data-testid='project-sidebar']")
    .getByText("New Project")
    .last()
    .dblclick();
  await page.getByTestId("input-project").fill(destinationProjectName);
  await page.keyboard.press("Enter");
  await expect(
    page.getByTestId(`sidebar-nav-${destinationProjectName}`),
  ).toBeVisible({ timeout: 10000 });

  // Go back to the source project where the flow currently lives.
  await page.getByTestId("sidebar-nav-Starter Project").click();
  await expect(
    page.getByTestId("list-card").filter({ hasText: uniqueFlowName }),
  ).toHaveCount(1, { timeout: 10000 });

  // Real HTML5 drag-and-drop: `dragTo()` populates `DataTransfer` so
  // the `use-on-file-drop.ts` handler reads `getData("flow")` and
  // triggers the folder-change mutation. `mouse.down/up` would NOT.
  await page
    .getByTestId("list-card")
    .filter({ hasText: uniqueFlowName })
    .first()
    .dragTo(page.getByTestId(`sidebar-nav-${destinationProjectName}`));

  // Click the destination folder and verify the moved flow is visible
  // WITHOUT a manual page refresh. This is the behavior that regresses
  // when the patch-flow cache invalidation is incomplete.
  await page.getByTestId(`sidebar-nav-${destinationProjectName}`).click();

  await expect(
    page.getByTestId("list-card").filter({ hasText: uniqueFlowName }),
  ).toHaveCount(1, { timeout: 10000 });

  // And the flow must NOT remain in the source project.
  await page.getByTestId("sidebar-nav-Starter Project").click();
  await expect(
    page.getByTestId("list-card").filter({ hasText: uniqueFlowName }),
  ).toHaveCount(0, { timeout: 10000 });
});
