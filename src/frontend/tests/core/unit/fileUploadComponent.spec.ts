import { expect, test } from "@playwright/test";
import path from "path";

test.skip("should be able to upload a file", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

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
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("file");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("dataFile")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByTestId("button_upload_file").click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(
    path.join(__dirname, "../../assets/test_file.txt"),
  );
  await page.getByText("test_file.txt").isVisible();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");

  await page
    .getByTestId("outputsChat Output")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("parse data");
  await page
    .getByTestId("helpersParse Data")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  let visibleElementHandle;

  const elementsFile = await page
    .getByTestId("handle-file-shownode-data-right")
    .all();

  for (const element of elementsFile) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  // Click and hold on the first element
  await visibleElementHandle.hover();
  await page.mouse.down();

  // Move to the second element

  const parseDataElement = await page
    .getByTestId("handle-parsedata-shownode-data-left")
    .all();

  for (const element of parseDataElement) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover();

  // Release the mouse
  await page.mouse.up();

  // Click and hold on the first element

  const parseDataOutputElement = await page
    .getByTestId("handle-parsedata-shownode-text-right")
    .all();

  for (const element of parseDataOutputElement) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await page.getByTitle("fit view").click();

  await visibleElementHandle.hover();
  await page.mouse.down();

  // Move to the second element
  const chatOutputElement = await page
    .getByTestId("handle-chatoutput-shownode-text-left")
    .all();

  for (const element of chatOutputElement) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover();

  // Release the mouse
  await page.mouse.up();

  await page.getByText("Playground", { exact: true }).last().click();

  await page.waitForSelector("text=Run Flow", {
    timeout: 30000,
  });

  await page.getByText("Run Flow", { exact: true }).click();

  await page.waitForTimeout(3000);
  expect(await page.getByText("this is a test file").isVisible()).toBe(true);
});
