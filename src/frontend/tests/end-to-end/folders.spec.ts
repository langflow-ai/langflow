import { test } from "@playwright/test";
import { readFileSync } from "fs";

test("CRUD folders", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByText("My Collection").nth(2).isVisible();
  await page.getByPlaceholder("Search flows").isVisible();
  await page.getByText("Flows").isVisible();
  await page.getByText("Components").isVisible();
  await page.getByText("All").first().isVisible();
  await page.getByText("Select All").isVisible();

  await page.getByTestId("add-folder-button").click();
  await page.getByText("New Folder").last().isVisible();
  await page.waitForTimeout(1000);
  await page.getByText("New Folder").last().dblclick();

  const element = await page.getByTestId("input-folder");
  await element.fill("new folder test name");

  await page.getByText("My Projects").last().click({
    force: true,
  });

  await page.getByText("new folder test name").last().waitFor({
    state: "visible",
    timeout: 30000,
  });

  await page
    .getByText("new folder test name")
    .last()
    .hover()
    .then(async () => {
      await page.getByTestId("btn-delete-folder").last().click();
    });

  await page.getByText("Delete").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Folder deleted successfully").isVisible();
});

test("add folder by drag and drop", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  const jsonContent = readFileSync(
    "tests/end-to-end/assets/collection.json",
    "utf-8",
  );

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
  await page.dispatchEvent(
    '//*[@id="root"]/div/div[1]/div[2]/div[3]/aside/nav/div/div[2]',
    "drop",
    {
      dataTransfer,
    },
  );

  await page.getByText("Getting Started").first().isVisible();
});

test("change flow folder", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByText("My Collection").nth(2).isVisible();
  await page.getByPlaceholder("Search flows").isVisible();
  await page.getByText("Flows").isVisible();
  await page.getByText("Components").isVisible();
  await page.getByText("All").first().isVisible();
  await page.getByText("Select All").isVisible();

  await page.getByTestId("add-folder-button").click();
  await page.getByText("New Folder").last().isVisible();
  await page.waitForTimeout(1000);
  await page.getByText("New Folder").last().dblclick();
  await page.getByTestId("input-folder").fill("new folder test name");
  await page.keyboard.press("Enter");
  await page.getByText("new folder test name").last().isVisible();

  await page.getByText("My Projects").last().click();
  await page.getByText("Basic Prompting").first().hover();
  await page.mouse.down();
  await page.getByText("test").first().hover();
  await page.mouse.up();
  await page.getByText("Basic Prompting").first().isVisible();
});
